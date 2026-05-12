import { useEffect, useState } from "react";
import { Chart } from "./components/Chart";
import { DirectionBadge } from "./components/DirectionBadge";
import { EarlySignalsFeed } from "./components/EarlySignalsFeed";
import { GuidancePanel } from "./components/GuidancePanel";
import { Watchlist } from "./components/Watchlist";
import { useStore } from "./state/store";
import { connectStream } from "./lib/ws";

export function App() {
  const symbol = useStore((s) => s.symbol);
  const tf = useStore((s) => s.tf);
  const setSymbolTf = useStore((s) => s.setSymbolTf);
  const [draftSymbol, setDraftSymbol] = useState(symbol);
  const [draftTf, setDraftTf] = useState(tf);

  useEffect(() => {
    setDraftSymbol(symbol);
    setDraftTf(tf);
  }, [symbol, tf]);

  useEffect(() => {
    const stop = connectStream(symbol, tf);
    return stop;
  }, [symbol, tf]);

  return (
    <div
      style={{
        height: "100vh",
        display: "grid",
        gridTemplateRows: "auto 1fr",
        gridTemplateColumns: "1fr 340px",
        background: "#0b0f17",
        color: "#e6edf3",
        fontFamily:
          "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      <header
        style={{
          gridColumn: "1 / span 2",
          padding: "10px 16px",
          borderBottom: "1px solid #1f2937",
          background: "#0d1117",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <strong style={{ fontSize: 14, letterSpacing: 0.3 }}>
          <span style={{ color: "#3b82f6" }}>◆</span> Chart Pattern Intelligence
        </strong>
        <div style={{ width: 1, height: 20, background: "#1f2937", margin: "0 4px" }} />
        <input
          value={draftSymbol}
          onChange={(e) => setDraftSymbol(e.target.value.toUpperCase())}
          onKeyDown={(e) => {
            if (e.key === "Enter") setSymbolTf(draftSymbol, draftTf);
          }}
          style={inp}
          placeholder="symbol"
        />
        <select value={draftTf} onChange={(e) => setDraftTf(e.target.value)} style={inp}>
          {["1m", "5m", "15m", "1h", "4h", "1d"].map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
        <button onClick={() => setSymbolTf(draftSymbol, draftTf)} style={btn}>
          Apply
        </button>
        <div style={{ flex: 1 }} />
        <DirectionBadge />
      </header>
      <main style={{ position: "relative", minWidth: 0, minHeight: 0 }}>
        <Chart />
      </main>
      <aside
        style={{
          borderLeft: "1px solid #1f2937",
          background: "#0d1117",
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
        }}
      >
        <Watchlist />
        <EarlySignalsFeed />
        <GuidancePanel />
      </aside>
    </div>
  );
}

const inp: React.CSSProperties = {
  background: "#161b22",
  color: "#e6edf3",
  border: "1px solid #30363d",
  borderRadius: 6,
  padding: "5px 10px",
  fontSize: 13,
  outline: "none",
};
const btn: React.CSSProperties = {
  ...inp,
  cursor: "pointer",
  background: "#1f6feb",
  borderColor: "#1f6feb",
  fontWeight: 500,
};
