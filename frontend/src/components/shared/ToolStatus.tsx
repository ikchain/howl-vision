import { Loader2, Check } from "lucide-react";
import type { ActiveTool } from "../../types";

const TOOL_LABELS: Record<string, string> = {
  classify_dermatology: "Analyzing dermatology image",
  detect_parasites: "Detecting blood parasites",
  segment_ultrasound: "Segmenting ultrasound image",
  search_clinical_cases: "Searching clinical cases",
  calculate_dosage: "Calculating dosage",
  check_drug_interactions: "Checking drug interactions",
};

function getLabel(name: string): string {
  return TOOL_LABELS[name] ?? `Running ${name}`;
}

interface Props {
  tools: ActiveTool[];
}

export default function ToolStatus({ tools }: Props) {
  if (tools.length === 0) return null;

  return (
    <div className="flex flex-col gap-1 py-2 px-3 rounded-lg bg-ocean-surface border border-ocean-border text-sm">
      {tools.map((tool) => (
        <div key={tool.name} className="flex items-center gap-2">
          {tool.status === "running" ? (
            <Loader2 className="w-3.5 h-3.5 text-amber-400 animate-spin" />
          ) : (
            <Check className="w-3.5 h-3.5 text-teal-text" />
          )}
          <span className={tool.status === "running" ? "text-amber-400" : "text-teal-text"}>
            {getLabel(tool.name)}
          </span>
        </div>
      ))}
    </div>
  );
}
