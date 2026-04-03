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

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex gap-2">
          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-emerald-400">
            {SOURCE_LABELS[result.source] ?? result.source}
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400">
            {result.record_type}
          </span>
        </div>
        <span className="text-xs text-gray-500">
          Score: {scorePercent}%
        </span>
      </div>
      <p className="text-sm text-gray-300 line-clamp-3">{result.text}</p>
      <p className="text-xs text-gray-600 mt-2">{result.id}</p>
    </div>
  );
}
