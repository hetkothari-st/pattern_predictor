import { useEffect, useState } from "react";
import { useStore } from "../state/store";

interface WatchlistItem {
  symbol: string;
  tf: string;
  top_pattern: string | null;
  top_direction: "bullish" | "bearish" | null;
  top_confidence: number | null;
  top_status: "forming" | "completed" | null;
}

export function Watchlist() {
  const symbol = useStore((s) => s.symbol);
  const tf = useStore((s) => s.tf);
  const setSymbolTf = useStore((s) => s.setSymbolTf);
  const [items, setItems] = useState<WatchlistItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetch("/api/watchlist")
        .then((r) => r.json())
        .then((j) => {
          if (!cancelled) setItems(j.items ?? []);
        })
        .catch(() => {});
    load();
    const id = setInterval(load, 4000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (items.length === 0) {
    return (
      <div style={{ padding: 12, opacity: 0.6, fontSize: 13 }}>
        No streams yet. Subscribe via MT_SUBSCRIPTIONS or POST a tick.
      </div>
    );
  }

  return (
    <div style={{ padding: 8, borderBottom: "1px solid #30363d" }}>
      <div style={{ fontSize: 11, opacity: 0.6, marginBottom: 4, letterSpacing: 0.5 }}>
        WATCHLIST
      </div>
      {items.map((it) => {
        const active = it.symbol === symbol && it.tf === tf;
        const dotColor =
          it.top_direction === "bullish"
            ? "#3fb950"
            : it.top_direction === "bearish"
              ? "#f85149"
              : "#30363d";
        return (
          <button
            key={`${it.symbol}-${it.tf}`}
            onClick={() => setSymbolTf(it.symbol, it.tf)}
            style={{
              display: "flex",
              width: "100%",
              alignItems: "center",
              gap: 8,
              padding: "6px 8px",
              marginBottom: 2,
              background: active ? "#1f2937" : "transparent",
              border: "1px solid",
              borderColor: active ? "#3b82f6" : "transparent",
              borderRadius: 4,
              color: "#e6edf3",
              cursor: "pointer",
              textAlign: "left",
              fontSize: 13,
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: dotColor,
                flexShrink: 0,
              }}
            />
            <span style={{ flex: 1, fontWeight: 500 }}>{it.symbol}</span>
            <span style={{ opacity: 0.5, fontSize: 11 }}>{it.tf}</span>
            {it.top_confidence !== null && (
              <span style={{ opacity: 0.7, fontSize: 11 }}>
                {(it.top_confidence * 100).toFixed(0)}%
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
