import type { CaseResult } from "../../types";

interface Props {
  result: CaseResult;
}

const SOURCE_LABELS: Record<string, string> = {
  vetclin: "Clinical",
  vetmed: "Narrative",
  phs: "Symptoms",
  qa: "Q&A",
  vha: "Assessment",
  adp: "Prediction",
  vpc: "PetCare",
};

export default function CaseCard({ result }: Props) {
  const scorePercent = Math.round(result.score * 100);

  const scoreColor =
    result.score >= 0.8
      ? "text-teal-light bg-teal/10"
      : result.score >= 0.5
      ? "text-amber-400 bg-amber-400/10"
      : "text-content-muted bg-ocean-elevated";

  return (
    <div className="bg-ocean-surface border border-ocean-border rounded-lg p-4 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-teal/5 transition-all duration-200">
      <div className="flex items-center justify-between mb-2">
        <div className="flex gap-2">
          <span className="text-xs px-2 py-0.5 rounded-full bg-ocean-elevated text-teal-text">
            {SOURCE_LABELS[result.source] ?? result.source}
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-ocean-elevated text-content-secondary">
            {result.record_type}
          </span>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-md ${scoreColor}`}>
          Score: {scorePercent}%
        </span>
      </div>
      <p className="text-sm text-content-primary line-clamp-3">{result.text}</p>
      <p className="text-xs text-content-muted mt-2">{result.id}</p>
    </div>
  );
}
