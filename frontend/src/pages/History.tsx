import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { getAnalyses } from "../lib/db";
import { UrgencyBadge } from "../components/shared/UrgencyBadge";
import { ResultCard } from "../components/shared/ResultCard";
import type { AnalysisRecord } from "../types";

export default function History() {
  const [records, setRecords] = useState<AnalysisRecord[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<AnalysisRecord | null>(null);

  useEffect(() => {
    setLoading(true);
    getAnalyses(filter === "all" ? undefined : filter)
      .then(setRecords)
      .catch(() => setRecords([]))
      .finally(() => setLoading(false));
  }, [filter]);

  return (
    <div className="py-6 px-4">
      <h1 className="text-lg font-bold mb-1">Analysis History</h1>
      <p className="text-xs text-content-muted mb-4">Stored locally on this device</p>

      <div className="flex gap-2 mb-4">
        {["all", "canine", "feline"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-xs transition-colors ${
              filter === f ? "bg-teal/20 text-teal-text" : "bg-ocean-surface text-content-muted"
            }`}
          >
            {f === "all" ? "All" : f === "canine" ? "Dogs" : "Cats"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-2 h-2 rounded-full bg-teal animate-pulse" />
        </div>
      ) : records.length === 0 ? (
        <p className="text-sm text-content-muted text-center py-12">
          No analyses yet. Go to Capture to start.
        </p>
      ) : (
        <div className="space-y-2">
          {records.map((r) => (
            <button
              key={r.id}
              onClick={() => r.fullResult && setSelected(r)}
              className="w-full flex items-center gap-3 bg-ocean-surface rounded-lg p-3 border border-ocean-border text-left hover:border-teal/40 transition-colors"
            >
              <img
                src={r.thumbnailDataUrl}
                alt=""
                className="w-12 h-12 rounded-lg object-cover flex-shrink-0"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-content-primary truncate">
                    {r.classification.replace(/_/g, " ")}
                  </span>
                  <UrgencyBadge urgency={r.urgency} />
                </div>
                <p className="text-xs text-content-muted truncate">{r.narrativeSummary}</p>
              </div>
              <span className="text-[10px] text-content-muted whitespace-nowrap">
                {new Date(r.timestamp).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                {" "}
                {new Date(r.timestamp).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Detail modal */}
      {selected?.fullResult && (
        <div
          className="fixed inset-0 z-50 bg-black/60 flex items-end sm:items-center justify-center"
          onClick={() => setSelected(null)}
        >
          <div
            className="bg-ocean-deep w-full sm:max-w-lg max-h-[85vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-ocean-deep/95 backdrop-blur-sm flex items-center justify-between px-4 py-3 border-b border-ocean-border">
              <span className="text-sm font-semibold text-content-primary">
                {new Date(selected.timestamp).toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })}
                {" "}
                {new Date(selected.timestamp).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
              </span>
              <button onClick={() => setSelected(null)} className="p-1 text-content-muted hover:text-content-primary">
                <X size={20} />
              </button>
            </div>
            <div className="p-4">
              <ResultCard result={selected.fullResult} previewUrl={selected.thumbnailDataUrl} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
