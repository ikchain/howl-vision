import { useState, useRef, useCallback, useEffect } from "react";
import { Upload, RotateCcw } from "lucide-react";
import { streamChat } from "../lib/sse";
import { fileToBase64, MAX_IMAGE_SIZE_BYTES } from "../lib/api";
import { compressImage } from "../lib/image";
import type { ActiveTool } from "../types";
import MarkdownRenderer from "../components/shared/MarkdownRenderer";
import ToolStatus from "../components/shared/ToolStatus";

const AUTO_MESSAGE =
  "Analyze this clinical image and provide a differential diagnosis with findings, differentials, recommendation, and pharmacology if applicable.";

type Status = "idle" | "analyzing" | "done" | "error";

export default function ImageDx() {
  const [status, setStatus] = useState<Status>("idle");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState("");
  const [activeTools, setActiveTools] = useState<ActiveTool[]>([]);
  const [errorMsg, setErrorMsg] = useState("");
  const [dragOver, setDragOver] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  // Track the blob URL so reset() + unmount can revoke it. Earlier versions
  // leaked a URL per upload; revocation now happens on reset and on unmount.
  const previewUrlRef = useRef<string | null>(null);

  const analyze = useCallback(async (file: File) => {
    let processed: File = file;
    try {
      const result = await compressImage(file);
      processed = result.file;
      console.debug(
        `[image] ${result.beforeBytes} -> ${result.afterBytes} bytes` +
          (result.skipped ? ` (skipped: ${result.reason})` : ""),
      );
    } catch (e) {
      console.warn("[image] compressImage threw, using original file:", e);
    }

    if (processed.size > MAX_IMAGE_SIZE_BYTES) {
      setErrorMsg(
        `Image too large (${(processed.size / 1024 / 1024).toFixed(1)} MB). Try a smaller photo.`,
      );
      setStatus("error");
      return;
    }

    const base64 = await fileToBase64(processed);
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    const url = URL.createObjectURL(processed);
    previewUrlRef.current = url;
    setPreviewUrl(url);
    setResult("");
    setActiveTools([]);
    setErrorMsg("");
    setStatus("analyzing");

    abortRef.current = streamChat(
      { message: AUTO_MESSAGE, image_b64: base64, history: [] },
      {
        onToolStatus(tool, toolStatus) {
          setActiveTools((prev) => {
            const existing = prev.find((t) => t.name === tool);
            if (existing) return prev.map((t) => t.name === tool ? { ...t, status: toolStatus } : t);
            return [...prev, { name: tool, status: toolStatus }];
          });
        },
        onToken(content) {
          setResult((prev) => prev + content);
        },
        onDone() {
          setActiveTools([]);
          setStatus("done");
        },
        onError(message) {
          setErrorMsg(message);
          setStatus("error");
        },
      },
    );
  }, []);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file?.type.startsWith("image/")) analyze(file);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) analyze(file);
    e.target.value = "";
  }

  function reset() {
    abortRef.current?.abort();
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setStatus("idle");
    setPreviewUrl(null);
    setResult("");
    setActiveTools([]);
    setErrorMsg("");
  }

  // Revoke any outstanding blob URL on unmount.
  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    };
  }, []);

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      <h1 className="text-xl font-bold mb-1">Image Diagnosis</h1>
      <p className="text-sm text-content-muted mb-6">
        Upload a clinical photo for instant AI-powered analysis.
      </p>

      {status === "idle" ? (
        <>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="hidden"
          />
          <div
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl p-16 flex flex-col items-center gap-3 cursor-pointer transition-colors ${
              dragOver
                ? "border-teal bg-teal/5"
                : "border-ocean-border hover:border-ocean-border-hover"
            }`}
          >
            <Upload className="w-8 h-8 text-content-secondary" />
            <p className="text-sm text-content-muted">
              Drag & drop an image here, or click to browse
            </p>
            <p className="text-xs text-content-secondary">
              Photos are resized automatically before upload
            </p>
          </div>
        </>
      ) : (
        <div className="space-y-4">
          {previewUrl && (
            <img
              src={previewUrl}
              alt="Clinical image"
              className="max-h-64 rounded-xl border border-ocean-elevated object-contain"
            />
          )}

          {activeTools.length > 0 && <ToolStatus tools={activeTools} />}

          {result && (
            <div className="bg-ocean-surface border border-ocean-elevated rounded-xl p-5 border-t-2 border-teal">
              <MarkdownRenderer
                content={result}
                streaming={status === "analyzing"}
              />
            </div>
          )}

          {status === "error" && (
            <p className="text-red-400 text-sm">{errorMsg}</p>
          )}

          {(status === "done" || status === "error") && (
            <button
              onClick={reset}
              className="flex items-center gap-2 text-sm text-content-muted hover:text-teal-text transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              Analyze another image
            </button>
          )}
        </div>
      )}
    </div>
  );
}
