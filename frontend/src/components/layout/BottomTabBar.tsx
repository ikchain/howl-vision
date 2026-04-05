import { NavLink } from "react-router-dom";
import { Camera, Clock, Info } from "lucide-react";

const TABS = [
  { to: "/capture", icon: Camera, label: "Capture" },
  { to: "/history", icon: Clock, label: "History" },
  { to: "/about", icon: Info, label: "About" },
] as const;

export function BottomTabBar() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-ocean-surface border-t border-ocean-border flex justify-around py-2 px-4">
      {TABS.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `flex flex-col items-center gap-0.5 px-3 py-1 text-xs transition-colors ${
              isActive ? "text-teal-text" : "text-content-muted"
            }`
          }
        >
          <Icon size={20} />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
