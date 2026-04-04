import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Sidebar } from "./components/layout/Sidebar";
import VetChat from "./pages/VetChat";
import ImageDx from "./pages/ImageDx";
import CaseViewer from "./pages/CaseViewer";
import { About } from "./pages/About";
import { NotFound } from "./pages/NotFound";

function AppLayout() {
  const location = useLocation();
  const showSidebar = location.pathname !== "/" && location.pathname !== "/404";

  return (
    <div className="flex min-h-screen bg-ocean-deep text-content-primary font-sans">
      {showSidebar && <Sidebar />}
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<About />} />
          <Route path="/chat" element={<VetChat />} />
          <Route path="/diagnose" element={<ImageDx />} />
          <Route path="/cases" element={<CaseViewer />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
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
