
import { NextRequest, NextResponse } from "next/server";
import { exec } from "child_process";
import fs from "fs";
import path from "path";
import util from "util";

const execAsync = util.promisify(exec);

// Define Error Contract Types locally to match backend
type AnimationError = {
    status: "error";
    error_code: string;
    error_message: string;
    job_id?: string;
};

type AnimationSuccess = {
    status: "completed";
    job_id: string;
    output: {
        video: string;
        thumbnail: string;
    };
    meta: any;
};

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const { start_panel, end_panel, overrides, timing, seed } = body;

        // Validate inputs
        if (!start_panel || !end_panel) {
            return NextResponse.json(
                { status: "error", error_code: "INVALID_INPUT", error_message: "Missing panels" },
                { status: 400 }
            );
        }

        // Construct Payload for worker
        // Note: We expect start_panel and end_panel to be absolute paths on the server
        // or relative paths that the worker can resolve.
        const jobPayload = {
            start_panel, // e.g. "C:/.../uploads/file1.png"
            end_panel,
            overrides: overrides || {},
            timing: timing || { fps: 24, frames: 12 },
            seed: seed || 42,
        };

        const runId = Date.now().toString();
        const payloadPath = path.resolve("job_payload_" + runId + ".json");
        fs.writeFileSync(payloadPath, JSON.stringify(jobPayload));

        // Determine python path (assuming venv in project root)
        const pythonPath = path.resolve("venv", "Scripts", "python.exe"); // Windows assumption
        const workerPath = path.resolve("worker.py");

        const command = `"${pythonPath}" "${workerPath}" "${payloadPath}"`;

        // Execute Worker
        console.log("Executing:", command);
        const { stdout, stderr } = await execAsync(command);

        // Clean up payload file
        try { fs.unlinkSync(payloadPath); } catch (e) { }

        console.log("Worker Stdout:", stdout);

        // Parse JSON output from the worker (it prints JSON to stdout)
        // We need to find the JSON blob in the stdout. 
        // worker.py prints JSON at the end.
        // Let's rely on finding the last JSON object.
        const lines = stdout.trim().split("\n");
        let resultJson: AnimationSuccess | AnimationError | null = null;

        // Try to parse the full stdout first, or find the json block
        // Our worker prints formatted JSON, so we might need to parse the last valid JSON block.
        // Simplified strategy: The worker's `run_job` prints `print(json.dumps(result, indent=2))` at the very end.
        // We can try to regex match the JSON object.
        const jsonMatch = stdout.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
            try {
                resultJson = JSON.parse(jsonMatch[0]);
            } catch (e) {
                console.error("Failed to parse JSON from stdout", e);
            }
        }

        if (!resultJson) {
            return NextResponse.json(
                {
                    status: "error",
                    error_code: "WORKER_FAILURE",
                    error_message: "Worker did not return valid JSON.",
                    details: stderr || stdout
                },
                { status: 500 }
            );
        }

        if (resultJson.status === "error") {
            return NextResponse.json(resultJson, { status: 422 }); // Unprocessable Entity for logic errors
        }

        return NextResponse.json(resultJson);

    } catch (err: any) {
        console.error("Internal API Error:", err);
        return NextResponse.json(
            {
                status: "error",
                error_code: "INTERNAL_SERVER_ERROR",
                error_message: err.message
            },
            { status: 500 }
        );
    }
}
