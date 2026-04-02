import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import VetChat from "./pages/VetChat";
import ImageDx from "./pages/ImageDx";
import CaseViewer from "./pages/CaseViewer";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-950 text-gray-100">
        <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-6">
          <span className="font-bold text-lg tracking-tight">Howl Vision</span>
          <NavLink to="/" className={({ isActive }) => isActive ? "text-white" : "text-gray-400 hover:text-gray-200"}>Chat</NavLink>
          <NavLink to="/diagnose" className={({ isActive }) => isActive ? "text-white" : "text-gray-400 hover:text-gray-200"}>ImageDx</NavLink>
          <NavLink to="/cases" className={({ isActive }) => isActive ? "text-white" : "text-gray-400 hover:text-gray-200"}>Cases</NavLink>
        </nav>
        <main className="p-6">
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
