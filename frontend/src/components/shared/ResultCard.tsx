import type { AnalyzeResponse } from "../../types";
import { ConfidenceBar } from "./ConfidenceBar";
import { UrgencyBadge } from "./UrgencyBadge";
import MarkdownRenderer from "./MarkdownRenderer";

interface Props {
  result: AnalyzeResponse;
  previewUrl: string;
}

export function ResultCard({ result, previewUrl }: Props) {
  const { classification, narrative, urgency, rag_matches } = result;
  const lowConfidence = classification.confidence < 0.60;

  return (
    <div className={`rounded-xl border ${lowConfidence ? "border-red-500/40" : "border-ocean-elevated"} bg-ocean-surface overflow-hidden`}>
      {/* Header: image + classification */}
      <div className="flex gap-4 p-4">
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
      <div className={`border-t ${lowConfidence ? "border-red-500/20" : "border-teal/30"} p-4`}>
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
