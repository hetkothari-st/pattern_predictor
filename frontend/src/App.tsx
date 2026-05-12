import { useEffect, useMemo, useState } from "react";
import { Chart } from "./components/Chart";
import { DirectionBadge } from "./components/DirectionBadge";
import { EarlySignalsFeed } from "./components/EarlySignalsFeed";
import { GuidancePanel } from "./components/GuidancePanel";
import { BookInsight } from "./components/BookInsight";
import { CriticPanel } from "./components/CriticPanel";
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

function fmtVol(v: number | undefined) {
  if (v === undefined || !Number.isFinite(v)) return "—";
  if (v >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (v >= 1e6) return (v / 1e6).toFixed(2) + "M";
  if (v >= 1e3) return (v / 1e3).toFixed(2) + "K";
  return v.toFixed(0);
}

export function App() {
  const symbol = useStore((s) => s.symbol);
  const tf = useStore((s) => s.tf);
  const setSymbolTf = useStore((s) => s.setSymbolTf);
  const bars = useStore((s) => s.bars);
  const detections = useStore((s) => s.detections);

  const [now, setNow] = useState(new Date());
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = (typeof window !== "undefined" && localStorage.getItem(THEME_KEY)) as Theme | null;
    return stored === "light" || stored === "dark" ? stored : "dark";
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
  const dirCls = stats && stats.change >= 0 ? "bull-c" : stats ? "bear-c" : "";
  const arrow = stats && stats.change >= 0 ? "▲" : "▼";

  const counts = useMemo(() => {
    const arr = Object.values(detections);
    return {
      forming: arr.filter((d) => d.status === "forming").length,
      done: arr.filter((d) => d.status === "completed").length,
    };
  }, [detections]);

  return (
    <div className="shell">
      {/* row 1 — toolbar */}
      <header className="toolbar rise">
        <div className="brand">
          <div className="brand-mark">S</div>
          <div className="brand-col">
            <span className="brand-name">Sentinel</span>
            <span className="brand-sub">PI · v0.1</span>
          </div>
        </div>

        <div className="toolbar-zone">
          <SymbolPicker />
        </div>

        <div className="toolbar-zone flex">
          <DirectionBadge />
        </div>

        <div className="toolbar-zone">
          <span className="hint">
            <span className="kbd">⌘</span>
            <span className="kbd">K</span>
            <span>Command</span>
          </span>
        </div>

        <div className="toolbar-zone right">
          <button
            className="icon-btn"
            title={theme === "dark" ? "Switch to light" : "Switch to dark"}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </header>

      {/* row 2 — tape */}
      <div className="tape rise rise-1">
        <div className="tape-main">
          <div className="tape-sym">
            <span className="tape-sym-name">{symbol}</span>
            <div className="tape-sym-meta">
              <span className="tape-sym-tf">{tf}</span>
              <span className="tape-sym-tf">live</span>
            </div>
          </div>

          <div className="tape-price">
            <span className={`tape-price-last ${dirCls}`}>
              {fmtPrice(stats?.last.close)}
            </span>
            <span className={`tape-price-delta ${dirCls}`}>
              {stats && (
                <>
                  <span className={`tape-price-arrow ${dirCls}`}>{arrow}</span>
                  <span>
                    {stats.change >= 0 ? "+" : ""}
                    {fmtPrice(stats.change)}
                  </span>
                  <span style={{ opacity: 0.7 }}>
                    {stats.pct >= 0 ? "+" : ""}
                    {stats.pct.toFixed(2)}%
                  </span>
                </>
              )}
              {!stats && <span style={{ color: "var(--text-3)" }}>awaiting feed</span>}
            </span>
          </div>

          <div className="tape-stats">
            <Stat label="Open"  value={fmtPrice(stats?.last.open)} />
            <Stat label="High"  value={fmtPrice(stats?.hi)} cls="bull-c" />
            <Stat label="Low"   value={fmtPrice(stats?.lo)} cls="bear-c" />
            <Stat label="Vol"   value={fmtVol(stats?.vol)} />
          </div>
        </div>

        <div className="tape-side">
          <div className="tape-clock">
            <span>{now.toISOString().substring(11, 19)}</span>
            <span style={{ color: "var(--text-3)" }}>UTC</span>
          </div>
          <div className={`tape-conn ${live ? "" : "idle"}`}>
            <span className={`live-dot ${live ? "" : "idle"}`} />
            <span>Feed</span>
            <b>{live ? "Connected" : "Idle"}</b>
          </div>
        </div>
      </div>

      {/* row 3 col 1 — chart */}
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
          <span className="chart-tools-sep" />
          <span className="chart-meta">{symbol} · {tf} · candles</span>
        </div>
        <div className="chart-canvas">
          <Chart theme={theme} />
          <span className="bracket tl" />
          <span className="bracket tr" />
          <span className="bracket bl" />
          <span className="bracket br" />
          <RobotWidget />
        </div>
      </main>

      {/* row 3 col 2 — stacked side panel */}
      <aside className="aside rise rise-3">
        <div className="aside-body">
          <Section title="Watch" count={null}>
            <Watchlist />
          </Section>
          <Section title="Signals" count={counts.forming}>
            <EarlySignalsFeed />
          </Section>
          <Section title="Playbook" count={counts.done}>
            <GuidancePanel />
          </Section>
          <Section title="Reference" count={null}>
            <BookInsight />
          </Section>
          <Section title="Critic" count={null}>
            <CriticPanel />
          </Section>
        </div>
      </aside>

      {/* row 4 — status bar */}
      <footer className="statusbar">
        <div className="statusbar-item ok">
          <span className={`live-dot ${live ? "" : "idle"}`} />
          <span>Net</span>
          <b>{live ? "OK" : "—"}</b>
        </div>
        <div className="statusbar-item">
          <span>Bars</span>
          <b>{bars.length}</b>
        </div>
        <div className="statusbar-item">
          <span>Forming</span>
          <b>{counts.forming}</b>
        </div>
        <div className="statusbar-item">
          <span>Confirmed</span>
          <b>{counts.done}</b>
        </div>
        <span className="statusbar-spacer" />
        <div className="statusbar-item right">
          <span>Engine</span>
          <b>v0.1</b>
        </div>
        <div className="statusbar-item right">
          <b>{now.toLocaleTimeString("en-GB", { hour12: false })}</b>
        </div>
      </footer>
    </div>
  );
}

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count: number | null;
  children: React.ReactNode;
}) {
  return (
    <section className="section">
      <header className="section-head">
        <span className="section-bar" />
        <span className="section-title">{title}</span>
        {count !== null && count > 0 && <span className="section-count">{count}</span>}
      </header>
      <div className="section-body">{children}</div>
    </section>
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
