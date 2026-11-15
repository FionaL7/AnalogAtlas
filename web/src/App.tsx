import { Link, NavLink, Route, Routes } from "react-router-dom";

import { apiMode } from "./lib/api";
import { Atlas } from "./routes/Atlas";
import { CloseStudyPage } from "./routes/CloseStudy";
import { Data } from "./routes/Data";
import { Discoveries } from "./routes/Discoveries";
import { Methodology } from "./routes/Methodology";
import { SiteGuide } from "./routes/SiteGuide";
import { Sites } from "./routes/Sites";
import { Traps } from "./routes/Traps";

const link = ({ isActive }: { isActive: boolean }) =>
  `rounded px-2 py-1 text-sm ${isActive ? "bg-edge text-ink" : "text-muted hover:text-ink"}`;

const NAV: [string, string][] = [
  ["/sites", "Field guides"],
  ["/discoveries", "Discoveries"],
  ["/traps", "Traps"],
  ["/methodology", "Methodology"],
  ["/data", "Data"],
];

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="flex flex-wrap items-center gap-3 border-b border-edge px-4 py-3">
        <Link to="/" aria-label="AnalogAtlas home" className="text-xl font-bold hover:text-accent">
          AnalogAtlas
        </Link>
        <nav className="ml-auto flex flex-wrap items-center gap-1">
          <NavLink to="/" className={link} end>Atlas</NavLink>
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={to} className={link}>{label}</NavLink>
          ))}
          {/* Which backend is answering: a developer's aid, not something visitors need. */}
          {import.meta.env.DEV && (
            <span className="ml-2 rounded border border-edge px-1.5 py-0.5 text-xs text-muted">
              {apiMode()}
            </span>
          )}
        </nav>
      </header>
      <main className="p-4">
        <Routes>
          <Route path="/" element={<Atlas />} />
          <Route path="/sites" element={<Sites />} />
          <Route path="/sites/:id" element={<SiteGuide />} />
          <Route path="/discoveries" element={<Discoveries />} />
          <Route path="/close-study/:id" element={<CloseStudyPage />} />
          <Route path="/traps" element={<Traps />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/data" element={<Data />} />
          <Route path="*" element={<p className="text-sm text-muted">Not found.</p>} />
        </Routes>
      </main>
    </div>
  );
}
