import { useEffect, useMemo, useState } from "react";
import { Chart } from "./components/Chart";
import { DirectionBadge } from "./components/DirectionBadge";
import { EarlySignalsFeed } from "./components/EarlySignalsFeed";
import { GuidancePanel } from "./components/GuidancePanel";
import { BookInsight } from "./components/BookInsight";
import { RobotWidget } from "./components/RobotWidget";
import { SymbolPicker } from "./components/SymbolPicker";
import { Watchlist } from "./components/Watchlist";
import { useStore } from "./state/store";
import { connectStream } from "./lib/ws";

type Theme = "dark" | "light";

const THEME_KEY = "sentinel.theme";

function fmtPrice(p: number | undefined) {
  if (p === undefined || !Number.isFinite(p)) return "—";
  const abs = Math.abs(p);
  if (abs >= 1000) return p.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (abs >= 1) return p.toFixed(4);
  return p.toFixed(6);
}

export function App() {
  const symbol = useStore((s) => s.symbol);
  const tf = useStore((s) => s.tf);
  const setSymbolTf = useStore((s) => s.setSymbolTf);
  const bars = useStore((s) => s.bars);
  const [now, setNow] = useState(new Date());
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = (typeof window !== "undefined" && localStorage.getItem(THEME_KEY)) as Theme | null;
    if (stored === "light" || stored === "dark") return stored;
    return "dark";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    const stop = connectStream(symbol, tf);
    return stop;
  }, [symbol, tf]);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const stats = useMemo(() => {
    if (bars.length === 0) return null;
    const last = bars[bars.length - 1];
    const prev = bars.length > 1 ? bars[bars.length - 2] : last;
    const change = last.close - prev.close;
    const pct = prev.close ? (change / prev.close) * 100 : 0;
    const window = bars.slice(-60);
    const hi = Math.max(...window.map((b) => b.high));
    const lo = Math.min(...window.map((b) => b.low));
    const vol = window.reduce((s, b) => s + (b.volume ?? 0), 0);
    return { last, change, pct, hi, lo, vol };
  }, [bars]);

  const live = bars.length > 0;
  const dir = stats && stats.change >= 0 ? "bull-c" : "bear-c";

  return (
    <div className="shell">
      <header className="toolbar rise">
        <div className="brand">
          <div className="brand-mark">S</div>
          <div className="brand-col">
            <span className="brand-name">Sentinel</span>
            <span className="brand-sub">Pattern Intelligence</span>
          </div>
        </div>

        <SymbolPicker />

        <span className="toolbar-sep" />

        <DirectionBadge />

        <span className="toolbar-spacer" />

        <button
          className="icon-btn"
          title={theme === "dark" ? "Switch to light" : "Switch to dark"}
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
        </button>
      </header>

      <div className="tape rise rise-1">
        <div className="tape-sym">
          <span className="tape-sym-name">{symbol}</span>
          <span className="tape-sym-tf">{tf}</span>
        </div>

        <div className="tape-stats">
          <Stat label="Last" value={fmtPrice(stats?.last.close)} cls={dir} />
          <Stat
            label="Chg"
            value={
              stats
                ? `${stats.change >= 0 ? "+" : ""}${fmtPrice(stats.change)} (${stats.pct >= 0 ? "+" : ""}${stats.pct.toFixed(2)}%)`
                : "—"
            }
            cls={dir}
          />
          <Stat label="Open" value={fmtPrice(stats?.last.open)} />
          <Stat label="High" value={fmtPrice(stats?.hi)} />
          <Stat label="Low" value={fmtPrice(stats?.lo)} />
          <Stat
            label="Vol"
            value={stats ? stats.vol.toLocaleString("en-US", { maximumFractionDigits: 0 }) : "—"}
          />
        </div>

        <div className="tape-clock">
          <span className={`live-dot ${live ? "" : "idle"}`} />
          <span>{now.toISOString().substring(11, 19)} UTC</span>
        </div>
      </div>

      <main className="chart-area rise rise-2">
        <div className="chart-toolbar">
          {(["1m", "5m", "15m", "1h", "4h", "1d"] as const).map((v) => (
            <button
              key={v}
              className={`tf-pill ${tf === v ? "on" : ""}`}
              onClick={() => setSymbolTf(symbol, v)}
            >
              {v}
            </button>
          ))}
        </div>
        <div className="chart-canvas">
          <Chart theme={theme} />
          <RobotWidget />
        </div>
      </main>

      <aside className="aside rise rise-3">
        <Watchlist />
        <EarlySignalsFeed />
        <GuidancePanel />
        <BookInsight />
      </aside>

      <footer className="statusbar">
        <div className={`statusbar-item ${live ? "ok" : ""}`}>
          <span className={`live-dot ${live ? "" : "idle"}`} />
          <span>Feed</span>
          <b>{live ? "Connected" : "Idle"}</b>
        </div>
        <div className="statusbar-item">
          <span>Bars</span>
          <b>{bars.length}</b>
        </div>
        <div className="statusbar-item">
          <span>Tape</span>
          <b>{symbol} · {tf}</b>
        </div>
        <span className="statusbar-spacer" />
        <div className="statusbar-item">
          <span>Engine</span>
          <b>v0.1</b>
        </div>
        <div className="statusbar-item">
          <span>{now.toLocaleTimeString("en-GB", { hour12: false })}</span>
        </div>
      </footer>
    </div>
  );
}

function Stat({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <div className="tape-stat">
      <span className="tape-stat-label">{label}</span>
      <span className={`tape-stat-val ${cls ?? ""}`}>{value}</span>
    </div>
  );
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}
function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}
