import { BrowserRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./components/layout/Sidebar";
import VetChat from "./pages/VetChat";
import ImageDx from "./pages/ImageDx";
import CaseViewer from "./pages/CaseViewer";

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-gray-950 text-gray-100">
        <Sidebar />
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<VetChat />} />
            <Route path="/diagnose" element={<ImageDx />} />
            <Route path="/cases" element={<CaseViewer />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
