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

  return (
    <section className="aside-section">
      <div className="section-head">
        <span className="section-head-bar" />
        <span className="section-title">Watchlist</span>
        <span className="section-count">{items.length}</span>
      </div>

      {items.length === 0 ? (
        <div className="empty">
          No streams subscribed. Configure <code>MT_SUBSCRIPTIONS</code> or POST a tick to begin.
        </div>
      ) : (
        <>
          <div className="wl-head">
            <span />
            <span>Symbol</span>
            <span>TF</span>
            <span>Conf</span>
          </div>
          <div>
            {items.map((it) => {
              const active = it.symbol === symbol && it.tf === tf;
              const dotCls =
                it.top_direction === "bullish"
                  ? "dot bull"
                  : it.top_direction === "bearish"
                    ? "dot bear"
                    : "dot idle";
              return (
                <button
                  key={`${it.symbol}-${it.tf}`}
                  onClick={() => setSymbolTf(it.symbol, it.tf)}
                  className={`wl-row ${active ? "active" : ""}`}
                >
                  <span className={dotCls} />
                  <span className="wl-sym">{it.symbol}</span>
                  <span className="wl-tf">{it.tf}</span>
                  <span className="wl-conf">
                    {it.top_confidence !== null ? `${(it.top_confidence * 100).toFixed(0)}%` : "—"}
                  </span>
                </button>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
