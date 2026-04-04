import { MessageSquare, ScanLine, Database } from "lucide-react";
import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/chat", icon: MessageSquare, label: "VetChat" },
  { to: "/diagnose", icon: ScanLine, label: "ImageDx" },
  { to: "/cases", icon: Database, label: "Cases" },
];

export function Sidebar() {
  return (
    <aside className="w-64 sticky top-0 h-screen flex flex-col bg-gradient-to-b from-ocean-surface to-ocean-deep border-r border-ocean-border">
      {/* Logo */}
      <div className="px-5 py-6 text-center border-b border-ocean-border">
        <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-gradient-to-br from-teal-deep via-teal to-teal-light flex items-center justify-center shadow-lg shadow-teal/20">
          <img src="/logo-white.svg" alt="Howl Vision" className="w-7 h-7" />
        </div>
        <div className="text-sm font-semibold tracking-[2px] text-content-primary">
          HOWL VISION
        </div>
        <div className="text-[10px] tracking-[1px] text-teal-light mt-0.5">
          VETERINARY AI COPILOT
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-teal/15 text-teal-text"
                  : "text-content-secondary hover:text-content-primary hover:bg-ocean-elevated/50"
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-ocean-border flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-teal shadow-[0_0_6px_theme(colors.teal.DEFAULT)] animate-pulse" />
        <span className="text-[10px] text-content-muted">
          Gemma 4 E4B · Online
        </span>
      </div>
    </aside>
  );
}
