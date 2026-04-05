import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { BottomTabBar } from "./components/layout/BottomTabBar";
import Capture from "./pages/Capture";
import History from "./pages/History";
import { About } from "./pages/About";
import { NotFound } from "./pages/NotFound";

function AppLayout() {
  return (
    <div className="min-h-screen bg-ocean-deep text-content-primary font-sans pb-16">
      <main className="max-w-lg mx-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/capture" replace />} />
          <Route path="/capture" element={<Capture />} />
          <Route path="/history" element={<History />} />
          <Route path="/about" element={<About />} />
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
