import { useEffect, useState } from "react";
import { Chart } from "./components/Chart";
import { DirectionBadge } from "./components/DirectionBadge";
import { EarlySignalsFeed } from "./components/EarlySignalsFeed";
import { GuidancePanel } from "./components/GuidancePanel";
import { useStore } from "./state/store";
import { connectStream } from "./lib/ws";

export function App() {
  const symbol = useStore((s) => s.symbol);
  const tf = useStore((s) => s.tf);
  const setSymbolTf = useStore((s) => s.setSymbolTf);
  const [draftSymbol, setDraftSymbol] = useState(symbol);
  const [draftTf, setDraftTf] = useState(tf);

  useEffect(() => {
    const stop = connectStream(symbol, tf);
    return stop;
  }, [symbol, tf]);

  return (
    <div style={{ height: "100vh", display: "grid", gridTemplateRows: "auto 1fr", gridTemplateColumns: "1fr 320px" }}>
      <header
        style={{
          gridColumn: "1 / span 2",
          padding: "10px 14px",
          borderBottom: "1px solid #30363d",
          display: "flex",
          alignItems: "center",
          gap: 14,
        }}
      >
        <strong style={{ fontSize: 16 }}>Chart Pattern Intelligence</strong>
        <input
          value={draftSymbol}
          onChange={(e) => setDraftSymbol(e.target.value.toUpperCase())}
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
      <main style={{ position: "relative" }}>
        <Chart />
      </main>
      <aside
        style={{
          borderLeft: "1px solid #30363d",
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
        }}
      >
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
  borderRadius: 4,
  padding: "4px 8px",
};
const btn: React.CSSProperties = { ...inp, cursor: "pointer" };
