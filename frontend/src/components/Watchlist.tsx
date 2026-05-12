import { useEffect, useState } from "react";
import { useStore } from "../state/store";

interface WatchlistItem {
  symbol: string;
  tf: string;
  top_pattern: string | null;
  top_direction: "bullish" | "bearish" | null;
  top_confidence: number | null;
  top_status: "forming" | "completed" | null;
  spark?: number[];
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
      <div className="empty">
        No streams subscribed. Configure <code>MT_SUBSCRIPTIONS</code> or POST a tick to begin.
      </div>
    );
  }

  return (
    <>
      {items.map((it) => {
        const active = it.symbol === symbol && it.tf === tf;
        const dotCls =
          it.top_direction === "bullish"
            ? "dot bull"
            : it.top_direction === "bearish"
              ? "dot bear"
              : "dot idle";
        const confCls =
          it.top_direction === "bullish"
            ? "wl-conf bull-c"
            : it.top_direction === "bearish"
              ? "wl-conf bear-c"
              : "wl-conf";
        return (
          <button
            key={`${it.symbol}-${it.tf}`}
            onClick={() => setSymbolTf(it.symbol, it.tf)}
            className={`wl-row ${active ? "active" : ""}`}
          >
            <span className={dotCls} />
            <span className="wl-sym">{it.symbol}</span>
            <Spark values={it.spark} direction={it.top_direction} />
            <span className="wl-tf">{it.tf}</span>
            <span className={confCls}>
              {it.top_confidence !== null ? `${(it.top_confidence * 100).toFixed(0)}%` : "—"}
            </span>
          </button>
        );
      })}
    </>
  );
}


function Spark({
  values,
  direction,
}: {
  values?: number[];
  direction: "bullish" | "bearish" | null;
}) {
  const W = 60;
  const H = 20;
  const color =
    direction === "bullish"
      ? "var(--bull)"
      : direction === "bearish"
        ? "var(--bear)"
        : "var(--text-3)";

  const vs = values && values.length >= 2 ? values : null;
  if (!vs) {
    return (
      <svg className="wl-spark" width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
        <line
          x1="0"
          y1={H / 2}
          x2={W}
          y2={H / 2}
          stroke="var(--line-2)"
          strokeWidth="1"
          strokeDasharray="2 2"
        />
      </svg>
    );
  }

  const min = Math.min(...vs);
  const max = Math.max(...vs);
  const range = max - min || 1;
  const stepX = W / (vs.length - 1);
  const pts = vs
    .map((v, i) => `${(i * stepX).toFixed(1)},${(H - ((v - min) / range) * H).toFixed(1)}`)
    .join(" ");

  return (
    <svg className="wl-spark" width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
