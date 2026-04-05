import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { BottomTabBar } from "./components/layout/BottomTabBar";
import { ConnectionBadge } from "./components/layout/ConnectionBadge";
import Capture from "./pages/Capture";
import History from "./pages/History";
import { About } from "./pages/About";
import QRConnect from "./pages/QRConnect";
import { NotFound } from "./pages/NotFound";

function AppLayout() {
  return (
    <div className="min-h-screen bg-ocean-deep text-content-primary font-sans pb-16">
      <header className="sticky top-0 z-40 bg-ocean-deep/90 backdrop-blur-sm border-b border-ocean-border px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <img src="/logo-white.svg" alt="Howl Vision" className="w-5 h-5" />
          <span className="text-xs font-semibold tracking-widest text-content-primary">HOWL VISION</span>
        </div>
        <ConnectionBadge />
      </header>
      <main className="max-w-lg mx-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/capture" replace />} />
          <Route path="/capture" element={<Capture />} />
          <Route path="/history" element={<History />} />
          <Route path="/about" element={<About />} />
          <Route path="/connect" element={<QRConnect />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <BottomTabBar />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}
