import { useState, useEffect } from "react";
import { Wifi, WifiOff } from "lucide-react";
import { Link } from "react-router-dom";
import { watchServerConnection, getServerUrl } from "../../lib/connection";

export function ConnectionBadge() {
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    return watchServerConnection(setConnected);
  }, []);

  const hasUrl = !!getServerUrl();

  return (
    <Link to={connected ? "#" : "/connect"} className="no-underline">
      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium tracking-wide ${
        connected
          ? "bg-teal/15 text-teal-text"
          : "bg-amber-900/30 text-amber-400"
      }`}>
        {connected ? <Wifi size={12} /> : <WifiOff size={12} />}
        {connected ? "Clinic Hub" : hasUrl ? "Reconnecting..." : "Local AI"}
      </div>
    </Link>
  );
}
