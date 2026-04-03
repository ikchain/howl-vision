import { NavLink } from "react-router-dom";
import { MessageSquare, ScanLine, Database } from "lucide-react";

const NAV_ITEMS = [
  { to: "/", label: "VetChat", icon: MessageSquare },
  { to: "/diagnose", label: "ImageDx", icon: ScanLine },
  { to: "/cases", label: "Cases", icon: Database },
];

export default function Sidebar() {
  return (
    <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-screen sticky top-0">
      <div className="px-5 py-5">
        <h1 className="text-lg font-bold tracking-tight text-gray-100">
          Howl Vision
        </h1>
        <p className="text-xs text-gray-500 mt-0.5">Veterinary AI Copilot</p>
      </div>

      <nav className="flex-1 px-3 space-y-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-gray-800 text-emerald-400"
                  : "text-gray-400 hover:text-gray-100 hover:bg-gray-800/50"
              }`
            }
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-gray-800">
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Gemma 4 · Online</span>
        </div>
      </div>
    </aside>
  );
}
