import { AlertTriangle } from "lucide-react";
import type { AnalyzeResponse } from "../../types";
import { ConfidenceBar } from "./ConfidenceBar";
import { UrgencyBadge } from "./UrgencyBadge";
import MarkdownRenderer from "./MarkdownRenderer";

interface Props {
  result: AnalyzeResponse;
  previewUrl: string;
}

export function ResultCard({ result, previewUrl }: Props) {
  const { classification, narrative, urgency, rag_matches, source, fallback_reason } = result;
  const lowConfidence = classification.confidence < 0.60;
  const isOffline = source === "local_ai";
  const isSilentFallback = isOffline && !!fallback_reason;

  const borderClass = lowConfidence
    ? "border-red-500/40"
    : isOffline
      ? "border-gray-500/40"
      : "border-teal/40";

  return (
    <div className={`rounded-xl border ${borderClass} bg-ocean-surface overflow-hidden`}>
      {/* Source indicator */}
      <div className={`flex items-center gap-1.5 px-4 pt-3 ${isSilentFallback ? "text-amber-400" : isOffline ? "text-content-muted" : "text-teal-text"}`}>
        {isSilentFallback ? (
          <AlertTriangle size={12} className="text-amber-400 flex-shrink-0" />
        ) : (
          <div className={`w-1.5 h-1.5 rounded-full ${isOffline ? "bg-gray-400" : "bg-teal"}`} />
        )}
        <span className="text-[10px] font-medium uppercase tracking-wider">
          {isSilentFallback ? "Offline Fallback" : isOffline ? "Local AI" : "Clinic Hub"}
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
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-sm font-semibold text-content-primary">
              {classification.label.replace(/_/g, " ")}
            </span>
            <UrgencyBadge urgency={urgency} />
          </div>
          <ConfidenceBar value={classification.confidence} />
          {lowConfidence && (
            <p className="text-xs text-red-400 mt-1">Low confidence — consult a veterinarian</p>
          )}
        </div>
      </div>

      {/* Narrative */}
      <div className={`border-t ${lowConfidence ? "border-red-500/20" : isOffline ? "border-gray-500/20" : "border-teal/30"} p-4`}>
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
    </div>
  );
}
