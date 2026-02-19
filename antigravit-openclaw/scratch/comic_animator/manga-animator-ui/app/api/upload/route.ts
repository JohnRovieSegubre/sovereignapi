
import { NextRequest, NextResponse } from "next/server";
import { writeFile } from "fs/promises";
import path from "path";
import fs from "fs";

export async function POST(request: NextRequest) {
    const data = await request.formData();
    const file: File | null = data.get("file") as unknown as File;

    if (!file) {
        return NextResponse.json({ success: false, message: "No file uploaded" }, { status: 400 });
    }

    const bytes = await file.arrayBuffer();
    const buffer = Buffer.from(bytes);

    // Ensure uploads directory exists
    const uploadDir = path.resolve("public", "uploads");
    if (!fs.existsSync(uploadDir)) {
        fs.mkdirSync(uploadDir, { recursive: true });
    }

    const filename = Date.now() + "_" + file.name.replace(/\s/g, "_");
    const filepath = path.join(uploadDir, filename);

    await writeFile(filepath, buffer);

    // Return absolute path for the worker (since worker is local)
    // And also a public URL for the UI to preview (if we serve public/uploads)
    return NextResponse.json({
        success: true,
        filepath: filepath,
        url: `/uploads/${filename}`
    });
}
