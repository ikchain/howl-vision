import { AlertTriangle } from "lucide-react";
import type { AnalyzeResponse } from "../../types";
import { ConfidenceBar } from "./ConfidenceBar";
import { FeedbackPanel } from "./FeedbackPanel";
import { UrgencyBadge } from "./UrgencyBadge";
import MarkdownRenderer from "./MarkdownRenderer";

interface Props {
  result: AnalyzeResponse;
  previewUrl: string;
  /** Original File for feedback submission. Null when viewing from History. */
  imageFile?: File | null;
  species?: "canine" | "feline";
}

export function ResultCard({ result, previewUrl, imageFile, species = "canine" }: Props) {
  const {
    classification,
    narrative,
    urgency,
    rag_matches,
    source,
    fallback_reason,
    prediction_quality,
  } = result;
  const lowConfidence = classification.confidence < 0.60;
  const isOffline = source === "local_ai";
  const isSilentFallback = isOffline && !!fallback_reason;
  const isInconclusive = prediction_quality === "inconclusive";
  const isLowConf = prediction_quality === "low_confidence";

  const borderClass = isInconclusive
    ? "border-red-500/40"
    : isLowConf || lowConfidence
      ? "border-amber-500/40"
      : isOffline
        ? "border-gray-500/40"
        : "border-teal/40";

  return (
    <div className={`rounded-xl border ${borderClass} bg-ocean-surface overflow-hidden`}>
      {/* Source indicator */}
      <div className={`flex items-center gap-1.5 px-4 pt-3 ${
        isSilentFallback ? "text-amber-400"
        : isInconclusive ? "text-red-400"
        : isLowConf ? "text-amber-400"
        : isOffline ? "text-content-muted"
        : "text-teal-text"
      }`}>
        {isSilentFallback || isInconclusive || isLowConf ? (
          <AlertTriangle size={12} className="flex-shrink-0" />
        ) : (
          <div className={`w-1.5 h-1.5 rounded-full ${isOffline ? "bg-gray-400" : "bg-teal"}`} />
        )}
        <span className="text-[10px] font-medium uppercase tracking-wider">
          {isSilentFallback ? "Offline Fallback"
            : isInconclusive ? "Inconclusive"
            : isLowConf ? "Low Confidence"
            : isOffline ? "Local AI"
            : "Clinic Hub"}
        </span>
      </div>
      {isSilentFallback && (
        <p className="text-[10px] text-amber-400/80 px-4 mt-1">
          Server was unreachable — using local classification only (no AI reasoning).
        </p>
      )}

      {/* Header: image + classification */}
      <div className="flex gap-4 p-4 pt-2">
        <img src={previewUrl} alt="Analyzed" className="w-20 h-20 rounded-lg object-cover flex-shrink-0" />
        <div className="flex-1 min-w-0">
          {isInconclusive ? (
            <p className="text-sm text-content-muted">
              No clear match found
            </p>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="text-sm font-semibold text-content-primary">
                  {classification.label.replace(/_/g, " ")}
                </span>
                <UrgencyBadge urgency={urgency} />
              </div>
              <ConfidenceBar value={classification.confidence} />
              {lowConfidence && (
                <p className="text-[10px] text-red-400/80 mt-1">Low confidence — consult a veterinarian</p>
              )}
            </>
          )}
        </div>
      </div>

      {/* Inconclusive: "The model considered" top-3 */}
      {isInconclusive && classification.differentials && (
        <div className="border-t border-red-500/20 px-4 py-3">
          <h3 className="text-xs font-semibold text-content-muted mb-2 uppercase tracking-wider">
            The model considered
          </h3>
          <div className="space-y-1">
            {[
              { label: classification.label, confidence: classification.confidence },
              ...classification.differentials.slice(0, 2),
            ].map((p, i) => (
              <div key={i} className="flex justify-between text-xs">
                <span className="text-content-secondary">{p.label.replace(/_/g, " ")}</span>
                <span className="text-content-muted">{(p.confidence * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Narrative */}
      <div className={`border-t ${
        isInconclusive ? "border-red-500/20"
        : isLowConf || lowConfidence ? "border-amber-500/20"
        : isOffline ? "border-gray-500/20"
        : "border-teal/30"
      } p-4`}>
        <MarkdownRenderer content={narrative} streaming={false} />
      </div>

      {/* RAG matches (only when server provides them) */}
      {rag_matches.length > 0 && (
        <div className="border-t border-ocean-border p-4">
          <h3 className="text-xs font-semibold text-content-muted mb-2 uppercase tracking-wider">Similar Cases</h3>
          {rag_matches.map((m, i) => (
            <div key={i} className="text-xs text-content-secondary mb-1">
              <span className="text-teal-text">{(m.similarity * 100).toFixed(0)}%</span>{" "}
              — {m.summary.slice(0, 150)}
            </div>
          ))}
        </div>
      )}

      {/* Active learning feedback (spec D1 — low_confidence + inconclusive only) */}
      {(isInconclusive || isLowConf) && imageFile && (
        <FeedbackPanel
          analysisId={result.analysis_id}
          imageFile={imageFile}
          originalLabel={classification.label}
          originalConfidence={classification.confidence}
          predictionQuality={prediction_quality}
          species={species}
        />
      )}
    </div>
  );
}
