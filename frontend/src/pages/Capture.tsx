import { useState, useRef, useCallback, useEffect } from "react";
import { Camera, RotateCcw } from "lucide-react";
import { analyzeImage } from "../lib/analyze";
import { saveAnalysis } from "../lib/db";
import { getProfile } from "../lib/profile";
import { ResultCard } from "../components/shared/ResultCard";
import type { AnalyzeResponse } from "../types";

type Species = "canine" | "feline";
type Module = "dermatology" | "parasites";
type Status = "idle" | "loading_model" | "analyzing" | "done" | "error";

const MAX_IMAGE_SIZE = 5 * 1024 * 1024; // 5MB

const MODULE_OPTIONS: Array<{ value: Module; label: string }> = [
  { value: "dermatology", label: "Skin Lesion" },
  { value: "parasites", label: "Blood Sample" },
];

export default function Capture() {
  const profile = getProfile();
  const allowedModules = profile?.modules ?? ["dermatology", "parasites"];
  const cameraHint = profile?.cameraHint ?? "Take photo or choose from gallery";

  const [status, setStatus] = useState<Status>("idle");
  const [species, setSpecies] = useState<Species>("canine");
  const [module, setModule] = useState<Module>(allowedModules[0] as Module);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [saved, setSaved] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const previewUrlRef = useRef<string | null>(null);

  // Revoke object URL on unmount to prevent memory leaks (W3)
  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    };
  }, []);

  const handleFile = useCallback(async (file: File) => {
    // Clear stale state from any previous analysis before validation
    setResult(null);
    setErrorMsg("");
    setSaved(false);

    if (file.size > MAX_IMAGE_SIZE) {
      setErrorMsg("Image too large (max 5MB).");
      setStatus("error");
      return;
    }
    // Revoke previous URL before creating a new one
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    const url = URL.createObjectURL(file);
    previewUrlRef.current = url;
    setPreviewUrl(url);
    setStatus("analyzing");
    try {
      const response = await analyzeImage(file, species, module, setStatus);
      setResult(response);
      setStatus("done");
      saveAnalysis(file, response, species, module)
        .then(() => setSaved(true))
        .catch((err) => console.warn("Failed to save analysis to history:", err));
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Analysis failed");
      setStatus("error");
    }
  }, [species, module]);

  function reset() {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setStatus("idle");
    setPreviewUrl(null);
    setResult(null);
    setErrorMsg("");
    setSaved(false);
  }

  return (
    <div className="py-6 px-4 space-y-4">
      {/* Species + Module selector */}
      <div className="flex gap-2">
        <select
          value={species}
          onChange={(e) => setSpecies(e.target.value as Species)}
          className="flex-1 bg-ocean-surface border border-ocean-border rounded-lg px-3 py-2 text-sm text-content-primary"
        >
          <option value="canine">Dog</option>
          <option value="feline">Cat</option>
        </select>
        <select
          value={module}
          onChange={(e) => setModule(e.target.value as Module)}
          className="flex-1 bg-ocean-surface border border-ocean-border rounded-lg px-3 py-2 text-sm text-content-primary"
        >
          {MODULE_OPTIONS
            .filter((opt) => allowedModules.includes(opt.value))
            .map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
        </select>
      </div>

      {status === "idle" && (
        <>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) {
                handleFile(f).finally(() => {
                  // Clear after processing so the same file can be re-selected
                  if (inputRef.current) inputRef.current.value = "";
                });
              }
            }}
            className="hidden"
          />
          <button
            onClick={() => inputRef.current?.click()}
            className="w-full flex flex-col items-center gap-3 border-2 border-dashed border-ocean-border hover:border-teal rounded-xl p-12 transition-colors"
          >
            <Camera className="w-10 h-10 text-content-secondary" />
            <span className="text-sm text-content-muted">{cameraHint}</span>
            <span className="text-xs text-content-secondary">JPEG, PNG up to 5MB</span>
          </button>
        </>
      )}

      {(status === "analyzing" || status === "loading_model") && (
        <div className="flex flex-col items-center gap-3 py-12">
          {previewUrl && (
            <img src={previewUrl} alt="Analyzing" className="max-h-48 rounded-xl object-contain" />
          )}
          <div className="flex items-center gap-2 text-sm text-teal-text">
            <div className="w-2 h-2 rounded-full bg-teal animate-pulse" />
            {status === "loading_model" ? "Loading AI model..." : "Analyzing image..."}
          </div>
        </div>
      )}

      {status === "done" && result && previewUrl && (
        <div className="space-y-3">
          <ResultCard result={result} previewUrl={previewUrl} />
          <div className="flex items-center justify-between">
            <button
              onClick={reset}
              className="flex items-center gap-2 text-sm text-content-muted hover:text-teal-text transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              Analyze another image
            </button>
            {saved && (
              <span className="text-[10px] text-content-muted">Saved to history</span>
            )}
          </div>
        </div>
      )}

      {status === "error" && (
        <div className="text-center py-8">
          <p className="text-red-400 text-sm mb-3">{errorMsg}</p>
          <button onClick={reset} className="text-sm text-teal-text hover:underline">
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
