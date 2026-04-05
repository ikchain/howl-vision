interface Props { value: number }

export function ConfidenceBar({ value }: Props) {
  const pct = Math.round(value * 100);
  const color = value >= 0.85 ? "bg-teal" : value >= 0.60 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-ocean-elevated rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-content-muted w-10 text-right">{pct}%</span>
    </div>
  );
}
