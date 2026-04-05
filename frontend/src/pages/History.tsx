import { useState, useEffect } from "react";
import { getAnalyses } from "../lib/db";
import { UrgencyBadge } from "../components/shared/UrgencyBadge";
import type { AnalysisRecord } from "../types";

export default function History() {
  const [records, setRecords] = useState<AnalysisRecord[]>([]);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    getAnalyses(filter === "all" ? undefined : filter).then(setRecords);
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

      {records.length === 0 ? (
        <p className="text-sm text-content-muted text-center py-12">
          No analyses yet. Go to Capture to start.
        </p>
      ) : (
        <div className="space-y-2">
          {records.map((r) => (
            <div
              key={r.id}
              className="flex items-center gap-3 bg-ocean-surface rounded-lg p-3 border border-ocean-border"
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
                {new Date(r.timestamp).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
