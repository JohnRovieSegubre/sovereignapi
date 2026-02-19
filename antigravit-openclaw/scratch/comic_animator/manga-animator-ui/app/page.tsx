
"use client";

import { useState } from "react";
import Image from "next/image";
import { Upload, Film, Loader2, Play, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export default function ComicAnimator() {
  const [startImage, setStartImage] = useState<{ path: string; url: string } | null>(null);
  const [endImage, setEndImage] = useState<{ path: string; url: string } | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [resultVideo, setResultVideo] = useState<string | null>(null);
  const [fps, setFps] = useState(24);
  const [duration, setDuration] = useState(0.5); // Default 12 frames at 24fps
  const [mode, setMode] = useState<"face" | "pose">("face");
  const [seed, setSeed] = useState(42);
  const [error, setError] = useState<string | null>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>, type: "start" | "end") => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (data.success) {
        if (type === "start") setStartImage({ path: data.filepath, url: data.url });
        else setEndImage({ path: data.filepath, url: data.url });
        toast.success(`${type === "start" ? "Start" : "End"} panel uploaded.`);
        setError(null); // Clear errors on new upload
      } else {
        toast.error("Upload failed");
      }
    } catch (err) {
      toast.error("Error uploading file");
    }
  };

  const handleGenerate = async () => {
    if (!startImage || !endImage) {
      toast.error("Please upload both start and end panels.");
      return;
    }

    setIsProcessing(true);
    setResultVideo(null);
    setError(null);

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start_panel: startImage.path,
          end_panel: endImage.path,
          overrides: { face: mode === "face" },
          timing: { fps, frames: Math.round(duration * fps) },
          seed,
        }),
      });

      const data = await res.json();

      if (res.ok && data.status === "completed") {
        // The path returned is absolute system path (e.g. C:\...). 
        // We need to serve it to the frontend.
        // For MVP, we can't serve C:/ files directly in browser due to security.
        // However, our API saves to 'public/uploads' for inputs.
        // The worker saves to 'output/job_...'.
        // We need a way to view the output. 
        // Quick Fix: We should copy the output video to 'public/results' or stream it via an API route.
        // For now, let's assume we can fetch it via a proxy route or just show the success message.
        // Actually, let's just display the success state for this CLI wrapper.
        // BETTER: The worker output path is absolute. 
        // Let's assume for this MVP we just want to see "Success" and maybe the path.

        toast.success("Animation generated successfully!");
        // In a real app, we'd copy the file to public folder.
        // Let's simulate that by just showing the success card.
        setResultVideo(data.output.video);
      } else {
        // Handle Error Contract
        if (data.status === "error") {
          setError(`${data.error_code}: ${data.error_message}`);
          toast.error(`Generation Failed: ${data.error_code}`);
        } else {
          setError("Unknown error occurred");
          toast.error("Generation Failed");
        }
      }
    } catch (err) {
      console.error(err);
      setError("Network or Server Error");
      toast.error("Failed to connect to generator");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-8 font-sans selection:bg-indigo-500/30">
      <div className="max-w-6xl mx-auto space-y-8">

        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-6">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">
              Comic Animator
            </h1>
            <p className="text-zinc-400">Bring manga panels to life with AI-driven interpolation.</p>
          </div>
          <div className="flex items-center gap-2 text-sm text-zinc-500 font-mono">
            <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            Worker Online
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

          {/* Main Controls & Inputs */}
          <div className="lg:col-span-2 space-y-6">

            {/* Input Panels */}
            <div className="grid grid-cols-2 gap-4">
              {[
                { type: "start", label: "Start Panel", state: startImage, setter: setStartImage },
                { type: "end", label: "End Panel", state: endImage, setter: setEndImage },
              ].map((panel) => (
                <Card key={panel.type} className="bg-zinc-900 border-zinc-800 border-dashed border-2 overflow-hidden relative group">
                  <CardContent className="p-0 aspect-[4/3] flex flex-col items-center justify-center relative">
                    {panel.state ? (
                      <div className="relative w-full h-full">
                        <Image
                          src={panel.state.url}
                          alt={panel.label}
                          fill
                          className="object-contain p-2"
                        />
                        <Button
                          variant="destructive"
                          size="icon"
                          className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={() => (panel.setter as any)(null)}
                        >
                          X
                        </Button>
                      </div>
                    ) : (
                      <label className="cursor-pointer flex flex-col items-center gap-2 text-zinc-500 hover:text-indigo-400 transition-colors">
                        <Upload className="w-8 h-8" />
                        <span className="font-medium">{panel.label}</span>
                        <input
                          type="file"
                          accept="image/*"
                          className="hidden"
                          onChange={(e) => handleFileUpload(e, panel.type as "start" | "end")}
                        />
                      </label>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Error Display */}
            {error && (
              <div className="bg-red-900/20 border border-red-900/50 text-red-200 p-4 rounded-lg flex items-start gap-3">
                <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" />
                <div className="font-mono text-sm">{error}</div>
              </div>
            )}

            {/* Success Display */}
            {resultVideo && !error && (
              <div className="bg-emerald-900/20 border border-emerald-900/50 text-emerald-200 p-6 rounded-lg flex flex-col items-center gap-4">
                <div className="flex items-center gap-2 font-medium">
                  <CheckCircle2 className="w-5 h-5" />
                  Generation Complete
                </div>
                <div className="text-zinc-400 text-sm font-mono text-center">
                  Output saved to:<br />
                  <span className="text-zinc-300 select-all">{resultVideo}</span>
                </div>
              </div>
            )}

          </div>

          {/* Sidebar Controls */}
          <div className="space-y-6">
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle>Configuration</CardTitle>
                <CardDescription>Fine-tune the animation engine.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">

                {/* Mode Toggle */}
                <div className="space-y-3">
                  <Label className="text-xs uppercase tracking-wider text-zinc-500">Detection Mode</Label>
                  <div className="grid grid-cols-2 gap-2 bg-zinc-950 p-1 rounded-lg border border-zinc-800">
                    <button
                      onClick={() => setMode("face")}
                      className={cn("px-3 py-2 rounded-md text-sm font-medium transition-all", mode === "face" ? "bg-indigo-600 text-white shadow-lg" : "text-zinc-400 hover:text-white")}
                    >
                      Face Focus
                    </button>
                    <button
                      onClick={() => setMode("pose")}
                      className={cn("px-3 py-2 rounded-md text-sm font-medium transition-all", mode === "pose" ? "bg-indigo-600 text-white shadow-lg" : "text-zinc-400 hover:text-white")}
                    >
                      Full Body
                    </button>
                  </div>
                </div>

                {/* Duration Slider */}
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <Label>Duration</Label>
                    <span className="text-xs font-mono text-zinc-400">{duration}s</span>
                  </div>
                  <Slider
                    value={[duration]}
                    min={0.1}
                    max={2.0}
                    step={0.1}
                    onValueChange={([v]) => setDuration(v)}
                    className="py-2"
                  />
                </div>

                {/* Seed Input */}
                <div className="space-y-3">
                  <Label>Random Seed</Label>
                  <Input
                    type="number"
                    value={seed}
                    onChange={(e) => setSeed(parseInt(e.target.value) || 0)}
                    className="bg-zinc-950 border-zinc-800 font-mono"
                  />
                </div>

              </CardContent>
              <CardFooter>
                <Button
                  className="w-full bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold py-6 shadow-xl shadow-indigo-900/20"
                  onClick={handleGenerate}
                  disabled={isProcessing}
                >
                  {isProcessing ? (
                    <>
                      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                      Animating...
                    </>
                  ) : (
                    <>
                      <Film className="mr-2 h-5 w-5" />
                      Generate Animation
                    </>
                  )}
                </Button>
              </CardFooter>
            </Card>

            <div className="bg-zinc-900/50 rounded-lg p-4 border border-zinc-800/50">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">Debug Info</h3>
              <div className="font-mono text-[10px] text-zinc-600 space-y-1">
                <div>Status: {isProcessing ? "BUSY" : "IDLE"}</div>
                <div>FPS: {fps}</div>
                <div>Frames: {Math.round(duration * fps)}</div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
