import { useState, useEffect } from "react";
import { X, FileText } from "lucide-react";
import { getAnalyses } from "../lib/db";
import { UrgencyBadge } from "../components/shared/UrgencyBadge";
import { ResultCard } from "../components/shared/ResultCard";
import { TriageResultCard } from "../components/shared/TriageResultCard";
import type { HistoryRecord, ImageAnalysisRecord, TriageRecord } from "../types";

export default function History() {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<HistoryRecord | null>(null);

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
          {records.map((r) =>
            // Switch on `kind` FIRST, before any other field. Type narrowing
            // is fragile if we check species or another field first
            // (senior-code-engineer catch).
            r.kind === "image" ? (
              <ImageRow key={r.id} record={r} onSelect={setSelected} />
            ) : (
              <TriageRow key={r.id} record={r} onSelect={setSelected} />
            ),
          )}
        </div>
      )}

      {/* Detail modal — full screen overlay above tab bar */}
      {selected && (
        <div className="fixed inset-0 z-50 bg-ocean-deep flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-ocean-border flex-shrink-0">
            <span className="text-sm font-semibold text-content-primary">
              {new Date(selected.timestamp).toLocaleDateString(undefined, {
                month: "long",
                day: "numeric",
                year: "numeric",
              })}{" "}
              {new Date(selected.timestamp).toLocaleTimeString(undefined, {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
            <button
              onClick={() => setSelected(null)}
              className="p-2 text-content-muted hover:text-content-primary"
            >
              <X size={20} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 pb-20">
            {selected.kind === "image" ? (
              selected.fullResult && (
                <ResultCard
                  result={selected.fullResult}
                  previewUrl={selected.thumbnailDataUrl}
                />
              )
            ) : (
              <div className="space-y-3">
                <blockquote className="border-l-2 border-teal/40 pl-3 text-sm italic text-content-secondary">
                  You wrote: {selected.symptomsText}
                </blockquote>
                <TriageResultCard result={selected.fullResult} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

interface RowProps<T extends HistoryRecord> {
  record: T;
  onSelect: (record: T) => void;
}

function ImageRow({ record, onSelect }: RowProps<ImageAnalysisRecord>) {
  return (
    <button
      onClick={() => onSelect(record)}
      className="w-full flex items-center gap-3 bg-ocean-surface rounded-lg p-3 border border-ocean-border text-left hover:border-teal/40 transition-colors"
    >
      <img
        src={record.thumbnailDataUrl}
        alt=""
        className="w-12 h-12 rounded-lg object-cover flex-shrink-0"
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-content-primary truncate">
            {record.classification.replace(/_/g, " ")}
          </span>
          <UrgencyBadge urgency={record.urgency} />
        </div>
        <p className="text-xs text-content-muted truncate">{record.narrativeSummary}</p>
      </div>
      <span className="text-[10px] text-content-muted whitespace-nowrap">
        {formatShort(record.timestamp)}
      </span>
    </button>
  );
}

function TriageRow({ record, onSelect }: RowProps<TriageRecord>) {
  // Visually distinct from ImageRow: FileText icon (no thumbnail) +
  // explicit "Symptom check" label so colorblind users + screen readers
  // can tell the kinds apart without relying on the icon alone.
  // Narrow the union: UrgencyBadge does not accept "unknown".
  const knownUrgency: "emergency" | "soon" | "monitor" | "healthy" | null =
    record.urgency === "unknown" ? null : record.urgency;
  return (
    <button
      onClick={() => onSelect(record)}
      className="w-full flex items-center gap-3 bg-ocean-surface rounded-lg p-3 border border-ocean-border text-left hover:border-teal/40 transition-colors"
    >
      <div className="w-12 h-12 rounded-lg bg-ocean-deep border border-ocean-border flex items-center justify-center flex-shrink-0">
        <FileText className="w-5 h-5 text-content-muted" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] uppercase tracking-wider text-content-muted">
            Symptom check
          </span>
          {knownUrgency && <UrgencyBadge urgency={knownUrgency} />}
        </div>
        <p className="text-xs text-content-secondary truncate">
          {record.topCondition ?? "No matching condition"}
        </p>
      </div>
      <span className="text-[10px] text-content-muted whitespace-nowrap">
        {formatShort(record.timestamp)}
      </span>
    </button>
  );
}

function formatShort(timestamp: number): string {
  const date = new Date(timestamp);
  const day = date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const time = date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return `${day} ${time}`;
}
