import { NavLink, Route, Routes } from "react-router-dom";

import { apiMode } from "./lib/api";
import { Atlas } from "./routes/Atlas";
import { Methodology } from "./routes/Methodology";

const link = ({ isActive }: { isActive: boolean }) =>
  `rounded px-2 py-1 text-sm ${isActive ? "bg-edge text-ink" : "text-muted hover:text-ink"}`;

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="flex flex-wrap items-center gap-3 border-b border-edge px-4 py-3">
        <strong className="text-base">AnalogAtlas</strong>
        <span className="hidden text-xs text-muted sm:inline">
          Earth analogs for Moon-base sites
        </span>
        <nav className="ml-auto flex items-center gap-1">
          <NavLink to="/" className={link} end>Atlas</NavLink>
          <NavLink to="/methodology" className={link}>Methodology</NavLink>
          <span className="ml-2 rounded border border-edge px-1.5 py-0.5 text-xs text-muted">
            {apiMode()}
          </span>
        </nav>
      </header>
      <main className="p-4">
        <Routes>
          <Route path="/" element={<Atlas />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="*" element={<p className="text-sm text-muted">Not found.</p>} />
        </Routes>
      </main>
    </div>
  );
}
