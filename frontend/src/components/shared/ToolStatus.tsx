import { Loader2, Check } from "lucide-react";
import type { ActiveTool } from "../../types";

const TOOL_LABELS: Record<string, string> = {
  classify_dermatology: "Analizando imagen dermatologica",
  detect_parasites: "Detectando parasitos en microscopio",
  segment_ultrasound: "Segmentando imagen de ultrasonido",
  search_clinical_cases: "Buscando casos clinicos similares",
  calculate_dosage: "Calculando dosificacion",
  check_drug_interactions: "Verificando interacciones farmacologicas",
};

function getLabel(name: string): string {
  return TOOL_LABELS[name] ?? `Ejecutando ${name}`;
}

interface Props {
  tools: ActiveTool[];
}

export default function ToolStatus({ tools }: Props) {
  if (tools.length === 0) return null;

  return (
    <div className="flex flex-col gap-1 py-2 px-3 rounded-lg bg-gray-900 border border-gray-800 text-sm">
      {tools.map((tool) => (
        <div key={tool.name} className="flex items-center gap-2">
          {tool.status === "running" ? (
            <Loader2 className="w-3.5 h-3.5 text-amber-400 animate-spin" />
          ) : (
            <Check className="w-3.5 h-3.5 text-gray-500" />
          )}
          <span className={tool.status === "running" ? "text-amber-400" : "text-gray-500"}>
            {getLabel(tool.name)}
          </span>
        </div>
      ))}
    </div>
  );
}
