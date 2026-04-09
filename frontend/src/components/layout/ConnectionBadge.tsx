import { useState, useEffect } from "react";
import { Wifi, WifiOff, AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";
import { watchServerConnection, getServerUrl, type ConnectionState } from "../../lib/connection";

const BADGE_CONFIG: Record<ConnectionState, {
  bg: string; text: string; icon: typeof Wifi; label: string;
}> = {
  connected:    { bg: "bg-teal/15",       text: "text-teal-text",  icon: Wifi,          label: "Clinic Hub" },
  degraded:     { bg: "bg-amber-900/30",  text: "text-amber-400",  icon: AlertTriangle, label: "Limited" },
  disconnected: { bg: "bg-amber-900/30",  text: "text-amber-400",  icon: WifiOff,       label: "" },
};

export function ConnectionBadge() {
  const [state, setState] = useState<ConnectionState>("disconnected");

  useEffect(() => {
    return watchServerConnection(setState);
  }, []);

  const hasUrl = !!getServerUrl();
  const cfg = BADGE_CONFIG[state];
  const Icon = cfg.icon;
  const label = state === "disconnected"
    ? (hasUrl ? "Reconnecting..." : "Local AI")
    : cfg.label;

  return (
    <Link to={state === "connected" ? "#" : "/connect"} className="no-underline">
      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium tracking-wide ${cfg.bg} ${cfg.text}`}>
        <Icon size={12} />
        {label}
      </div>
    </Link>
  );
}
