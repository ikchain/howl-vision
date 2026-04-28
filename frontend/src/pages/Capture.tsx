import {
  useState,
  useRef,
  useCallback,
  useEffect,
  type KeyboardEvent,
} from "react";
import { Camera, RotateCcw, FileText } from "lucide-react";
import { analyzeImage } from "../lib/analyze";
import { saveAnalysis, saveTriage } from "../lib/db";
import { getProfile } from "../lib/profile";
import { triage } from "../lib/triage";
import { compressImage } from "../lib/image";
import { MAX_IMAGE_SIZE_BYTES } from "../lib/api";
import { ResultCard } from "../components/shared/ResultCard";
import { TriageResultCard } from "../components/shared/TriageResultCard";
import type { AnalyzeResponse } from "../types";
import type { TriageResult } from "../lib/triage";

type Species = "canine" | "feline";
type Module = "dermatology" | "parasites";
type Mode = "photo" | "symptoms";
type Status =
  | "idle"
  | "preparing_image"  // compressImage in flight; label debounced to 300 ms
  | "loading_model"
  | "analyzing"
  | "checking_symptoms"
  | "still_working"
  | "done"
  | "error";

const MIN_SYMPTOMS_LEN = 5;
const MAX_SYMPTOMS_LEN = 2000;
// Show "Preparing image..." only if compression exceeds this debounce, so
// fast paths (typical photos, <300 ms on mid-range phones) don't flash the
// label. Pattern matches STILL_WORKING_DELAY_MS below.
const PREPARING_LABEL_DELAY_MS = 300;
// "Still working..." copy kicks in at 3.5s — long enough that the user
// understands something is in flight, short enough that the wait does not
// silently exhaust their patience.
const STILL_WORKING_DELAY_MS = 3500;

const MODULE_OPTIONS: Array<{ value: Module; label: string }> = [
  { value: "dermatology", label: "Skin Lesion" },
  { value: "parasites", label: "Blood Sample" },
];

const MODE_OPTIONS: Array<{ value: Mode; label: string; icon: typeof Camera }> = [
  { value: "photo", label: "Photo", icon: Camera },
  { value: "symptoms", label: "Symptoms", icon: FileText },
];

export default function Capture() {
  const profile = getProfile();
  const allowedModules = profile?.modules ?? ["dermatology", "parasites"];
  const cameraHint = profile?.cameraHint ?? "Take photo or choose from gallery";
  const triageHint = profile?.triageHint ?? "Describe what you're seeing";

  const [mode, setMode] = useState<Mode>("photo");
  const [status, setStatus] = useState<Status>("idle");
  const [species, setSpecies] = useState<Species>("canine");
  const [module, setModule] = useState<Module>(allowedModules[0] as Module);

  // Photo state
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageResult, setImageResult] = useState<AnalyzeResponse | null>(null);
  const [imageSaved, setImageSaved] = useState(false);
  const [currentFile, setCurrentFile] = useState<File | null>(null);

  // Symptoms state
  const [symptomsText, setSymptomsText] = useState("");
  const [triageResult, setTriageResult] = useState<TriageResult | null>(null);
  const [triageSaved, setTriageSaved] = useState(false);

  const [errorMsg, setErrorMsg] = useState("");
  const [showPreparingLabel, setShowPreparingLabel] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const previewUrlRef = useRef<string | null>(null);
  const stillWorkingTimerRef = useRef<number | null>(null);

  // Revoke object URL on unmount to prevent memory leaks (W3)
  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      if (stillWorkingTimerRef.current !== null) {
        clearTimeout(stillWorkingTimerRef.current);
      }
    };
  }, []);

  // Debounce the "Preparing image..." label: only surface it if compression
  // takes longer than PREPARING_LABEL_DELAY_MS. Prevents a flash on fast
  // paths while giving the user feedback when the wait is real.
  useEffect(() => {
    if (status !== "preparing_image") {
      setShowPreparingLabel(false);
      return;
    }
    const t = window.setTimeout(
      () => setShowPreparingLabel(true),
      PREPARING_LABEL_DELAY_MS,
    );
    return () => clearTimeout(t);
  }, [status]);

  // Reset all transient state. Called on mode toggle and on "Try again".
  // Toggling Photo↔Symptoms wipes both branches' state — two modes, two
  // contexts, no mixing (D15).
  const resetAll = useCallback(() => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    if (stillWorkingTimerRef.current !== null) {
      clearTimeout(stillWorkingTimerRef.current);
      stillWorkingTimerRef.current = null;
    }
    setStatus("idle");
    setPreviewUrl(null);
    setImageResult(null);
    setImageSaved(false);
    setCurrentFile(null);
    setSymptomsText("");
    setTriageResult(null);
    setTriageSaved(false);
    setErrorMsg("");
  }, []);

  const handleFile = useCallback(
    async (file: File) => {
      // Clear stale state from any previous analysis before compression
      setImageResult(null);
      setErrorMsg("");
      setImageSaved(false);

      // Enter preparing_image immediately. The label-debounce effect keeps
      // the UI quiet on fast compressions (<300 ms typical).
      setStatus("preparing_image");

      let processed: File = file;
      try {
        const result = await compressImage(file);
        processed = result.file;
        console.debug(
          `[image] ${result.beforeBytes} -> ${result.afterBytes} bytes` +
            (result.skipped ? ` (skipped: ${result.reason})` : ""),
        );
      } catch (e) {
        // compressImage only throws for programmer errors (bad opts). Fall
        // open: use the original file and rely on the hard-cap check below.
        console.warn("[image] compressImage threw, using original file:", e);
      }

      // currentFile must reflect what the analyze pipeline + the active
      // learning feedback flow actually saw. Setting it BEFORE compression
      // would desync the feedback image from the inference input.
      setCurrentFile(processed);

      // Safety net: compression should keep real photos <2 MB; this cap
      // covers the fail-open path where compression skipped.
      if (processed.size > MAX_IMAGE_SIZE_BYTES) {
        setErrorMsg(
          `Image too large (${(processed.size / 1024 / 1024).toFixed(1)} MB). ` +
            "Try a smaller photo.",
        );
        setStatus("error");
        return;
      }

      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      const url = URL.createObjectURL(processed);
      previewUrlRef.current = url;
      setPreviewUrl(url);
      setStatus("analyzing");
      try {
        const response = await analyzeImage(processed, species, module, setStatus);
        setImageResult(response);
        setStatus("done");
        saveAnalysis(processed, response, species, module)
          .then(() => setImageSaved(true))
          .catch((err) => console.warn("Failed to save analysis to history:", err));
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : "Analysis failed");
        setStatus("error");
      }
    },
    [species, module],
  );

  const handleSymptomsSubmit = useCallback(async () => {
    setTriageResult(null);
    setErrorMsg("");
    setTriageSaved(false);
    setStatus("checking_symptoms");
    // Schedule the "Still working..." copy change. The status update is
    // a UX promise, not a path indicator — it never mentions server or
    // offline (D8).
    stillWorkingTimerRef.current = window.setTimeout(() => {
      setStatus((prev) => (prev === "checking_symptoms" ? "still_working" : prev));
    }, STILL_WORKING_DELAY_MS);
    try {
      const response = await triage(species, symptomsText);
      if (stillWorkingTimerRef.current !== null) {
        clearTimeout(stillWorkingTimerRef.current);
        stillWorkingTimerRef.current = null;
      }
      setTriageResult(response);
      setStatus("done");
      saveTriage(species, symptomsText, response)
        .then(() => setTriageSaved(true))
        .catch((err) => console.warn("Failed to save triage to history:", err));
    } catch (err) {
      if (stillWorkingTimerRef.current !== null) {
        clearTimeout(stillWorkingTimerRef.current);
        stillWorkingTimerRef.current = null;
      }
      setErrorMsg(err instanceof Error ? err.message : "Triage failed");
      setStatus("error");
    }
  }, [species, symptomsText]);

  // ARIA radiogroup keyboard handler — roving tabindex pattern.
  const handleModeKeydown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const next: Mode = mode === "photo" ? "symptoms" : "photo";
      setMode(next);
      resetAll();
    },
    [mode, resetAll],
  );

  const handleModeClick = useCallback(
    (next: Mode) => {
      if (next === mode) return;
      setMode(next);
      resetAll();
    },
    [mode, resetAll],
  );

  const symptomsValid =
    symptomsText.trim().length >= MIN_SYMPTOMS_LEN &&
    symptomsText.length <= MAX_SYMPTOMS_LEN;

  return (
    <div className="py-6 px-4 space-y-4">
      {/* Species + Module selectors — context shared by both modes (D2 says
          they go ABOVE the toggle so a user changing modes does not lose
          species awareness). Module selector is hidden in symptoms mode. */}
      <div className="flex gap-2">
        <select
          value={species}
          onChange={(e) => setSpecies(e.target.value as Species)}
          aria-label="Species"
          className="flex-1 bg-ocean-surface border border-ocean-border rounded-lg px-3 py-2 text-sm text-content-primary"
        >
          <option value="canine">Dog</option>
          <option value="feline">Cat</option>
        </select>
        {mode === "photo" && (
          <select
            value={module}
            onChange={(e) => setModule(e.target.value as Module)}
            aria-label="Module"
            className="flex-1 bg-ocean-surface border border-ocean-border rounded-lg px-3 py-2 text-sm text-content-primary"
          >
            {MODULE_OPTIONS.filter((opt) => allowedModules.includes(opt.value)).map(
              (opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ),
            )}
          </select>
        )}
      </div>

      {/* Mode toggle — radiogroup ARIA pattern with roving tabindex.
          Arrows move between options, only the active button is in tab order. */}
      <div
        role="radiogroup"
        aria-label="Analysis mode"
        onKeyDown={handleModeKeydown}
        className="flex gap-1 bg-ocean-surface border border-ocean-border rounded-lg p-1"
      >
        {MODE_OPTIONS.map(({ value, label, icon: Icon }) => {
          const active = mode === value;
          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={active}
              tabIndex={active ? 0 : -1}
              onClick={() => handleModeClick(value)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-xs transition-colors ${
                active
                  ? "bg-teal/20 text-teal-text font-medium"
                  : "text-content-muted hover:text-content-secondary"
              }`}
            >
              <Icon size={14} />
              {label}
            </button>
          );
        })}
      </div>

      {/* PHOTO MODE */}
      {mode === "photo" && (
        <>
          {status === "idle" && (
            <>
              <input
                ref={inputRef}
                type="file"
                accept="image/*"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) {
                    handleFile(f).finally(() => {
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
                <span className="text-xs text-content-secondary">
                  Photos are resized automatically before upload
                </span>
              </button>
            </>
          )}

          {(status === "preparing_image" ||
            status === "analyzing" ||
            status === "loading_model") && (
            <div
              className="flex flex-col items-center gap-3 py-12"
              role="status"
              aria-live="polite"
            >
              {previewUrl && (
                <img
                  src={previewUrl}
                  alt="Analyzing"
                  className="max-h-48 rounded-xl object-contain"
                />
              )}
              <div className="flex items-center gap-2 text-sm text-teal-text">
                <div className="w-2 h-2 rounded-full bg-teal animate-pulse" />
                {status === "preparing_image"
                  ? showPreparingLabel
                    ? "Preparing image..."
                    : "" /* sub-debounce: keep indicator but suppress label */
                  : status === "loading_model"
                    ? "Loading AI model..."
                    : "Analyzing image..."}
              </div>
            </div>
          )}

          {status === "done" && imageResult && previewUrl && (
            <div className="space-y-3">
              <ResultCard result={imageResult} previewUrl={previewUrl} imageFile={currentFile} species={species} />
              <div className="flex items-center justify-between">
                <button
                  onClick={resetAll}
                  className="flex items-center gap-2 text-sm text-content-muted hover:text-teal-text transition-colors"
                >
                  <RotateCcw className="w-4 h-4" />
                  Analyze another image
                </button>
                {imageSaved && (
                  <span className="text-[10px] text-content-muted">Saved to history</span>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* SYMPTOMS MODE */}
      {mode === "symptoms" && (
        <>
          {(status === "idle" || status === "error") && (
            <div className="space-y-3">
              <div className="space-y-1">
                <textarea
                  value={symptomsText}
                  onChange={(e) => setSymptomsText(e.target.value)}
                  placeholder={triageHint}
                  minLength={MIN_SYMPTOMS_LEN}
                  maxLength={MAX_SYMPTOMS_LEN}
                  rows={5}
                  aria-label="Describe symptoms"
                  className="w-full bg-ocean-surface border border-ocean-border rounded-lg px-3 py-2 text-sm text-content-primary placeholder:text-content-muted resize-none focus:border-teal/60 focus:outline-none"
                />
                <div className="flex justify-end text-[10px] text-content-muted">
                  {symptomsText.length} / {MAX_SYMPTOMS_LEN}
                </div>
              </div>
              <button
                onClick={handleSymptomsSubmit}
                disabled={!symptomsValid}
                aria-disabled={!symptomsValid}
                className={`w-full py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  symptomsValid
                    ? "bg-teal/20 text-teal-text hover:bg-teal/30"
                    : "bg-ocean-surface text-content-muted cursor-not-allowed"
                }`}
              >
                Check symptoms
              </button>
            </div>
          )}

          {(status === "checking_symptoms" || status === "still_working") && (
            <div className="flex flex-col items-center gap-3 py-12">
              <div className="flex items-center gap-2 text-sm text-teal-text">
                <div className="w-2 h-2 rounded-full bg-teal animate-pulse" />
                {status === "still_working" ? "Still working..." : "Checking symptoms..."}
              </div>
            </div>
          )}

          {status === "done" && triageResult && (
            <div className="space-y-3">
              <TriageResultCard result={triageResult} />
              <div className="flex items-center justify-between">
                <button
                  onClick={resetAll}
                  className="flex items-center gap-2 text-sm text-content-muted hover:text-teal-text transition-colors"
                >
                  <RotateCcw className="w-4 h-4" />
                  Check another
                </button>
                {triageSaved && (
                  <span className="text-[10px] text-content-muted">Saved to history</span>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* Error state shared by both modes */}
      {status === "error" && errorMsg && (
        <div className="text-center py-4">
          <p className="text-red-400 text-sm mb-3">{errorMsg}</p>
          <button onClick={resetAll} className="text-sm text-teal-text hover:underline">
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
