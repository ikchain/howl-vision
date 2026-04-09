const URGENCY_CONFIG = {
  emergency: { label: "Emergency", color: "bg-red-600 text-white" },
  soon: { label: "See Vet Soon", color: "bg-amber-600 text-white" },
  monitor: { label: "Monitor", color: "bg-yellow-600 text-black" },
  healthy: { label: "Healthy", color: "bg-teal text-white" },
} as const;

type KnownUrgency = keyof typeof URGENCY_CONFIG;

interface Props { urgency: KnownUrgency | "unknown" }

export function UrgencyBadge({ urgency }: Props) {
  if (urgency === "unknown") return null;
  const { label, color } = URGENCY_CONFIG[urgency];
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${color}`}>
      {label}
    </span>
  );
}
