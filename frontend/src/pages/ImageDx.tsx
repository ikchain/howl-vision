import { useState, useRef, useCallback } from "react";
import { Upload, RotateCcw } from "lucide-react";
import { streamChat } from "../lib/sse";
import { fileToBase64, MAX_IMAGE_SIZE_BYTES } from "../lib/api";
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

  const analyze = useCallback(async (file: File) => {
    if (file.size > MAX_IMAGE_SIZE_BYTES) {
      setErrorMsg(`Image too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Max 5MB.`);
      setStatus("error");
      return;
    }

    const base64 = await fileToBase64(file);
    setPreviewUrl(URL.createObjectURL(file));
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
    setStatus("idle");
    setPreviewUrl(null);
    setResult("");
    setActiveTools([]);
    setErrorMsg("");
  }

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      <h1 className="text-xl font-bold mb-1">Image Diagnosis</h1>
      <p className="text-sm text-gray-400 mb-6">
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
                ? "border-emerald-500 bg-emerald-500/5"
                : "border-gray-700 hover:border-gray-500"
            }`}
          >
            <Upload className="w-8 h-8 text-gray-500" />
            <p className="text-sm text-gray-400">
              Drag & drop an image here, or click to browse
            </p>
            <p className="text-xs text-gray-600">JPEG, PNG up to 5MB</p>
          </div>
        </>
      ) : (
        <div className="space-y-4">
          {previewUrl && (
            <img
              src={previewUrl}
              alt="Clinical image"
              className="max-h-64 rounded-xl border border-gray-800 object-contain"
            />
          )}

          {activeTools.length > 0 && <ToolStatus tools={activeTools} />}

          {result && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
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
              className="flex items-center gap-2 text-sm text-gray-400 hover:text-emerald-400 transition-colors"
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
