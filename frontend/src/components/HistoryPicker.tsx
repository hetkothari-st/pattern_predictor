import { useEffect, useState } from "react";
import { useStore } from "../state/store";

const PRESETS = [
  { value: "live", label: "Live" },
  { value: "today", label: "Today" },
  { value: "1d", label: "1D" },
  { value: "7d", label: "7D" },
  { value: "30d", label: "30D" },
  { value: "90d", label: "90D" },
  { value: "1y", label: "1Y" },
] as const;

interface Bar {
  symbol: string;
  tf: string;
  ts: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closed: boolean;
}

export function HistoryPicker() {
  const symbol = useStore((s) => s.symbol);
  const tf = useStore((s) => s.tf);
  const mode = useStore((s) => s.historyMode);
  const setHistoryMode = useStore((s) => s.setHistoryMode);
  const applySnapshot = useStore((s) => s.applySnapshot);
  const [days, setDays] = useState<string[]>([]);

  // Refresh available days when symbol/tf changes.
  useEffect(() => {
    fetch(`/api/days?symbol=${encodeURIComponent(symbol)}&tf=${encodeURIComponent(tf)}&limit=60`)
      .then((r) => r.json())
      .then((j) => setDays(j.days ?? []))
      .catch(() => setDays([]));
  }, [symbol, tf]);

  // When a non-live mode is picked, fetch range and apply as snapshot.
  useEffect(() => {
    if (mode === "live") return;
    let cancelled = false;
    const params = new URLSearchParams({ symbol, tf });
    if (mode === "today" || /^\d{4}-\d{2}-\d{2}$/.test(mode)) {
      params.set("day", mode === "today" ? new Date().toISOString().slice(0, 10) : mode);
    } else {
      params.set("period", mode);
    }
    fetch(`/api/bars/range?${params.toString()}`)
      .then((r) => r.json())
      .then((j) => {
        if (cancelled) return;
        const bars = (j.bars ?? []) as Bar[];
        applySnapshot(bars, [], []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [mode, symbol, tf, applySnapshot]);

  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
      <select
        value={PRESETS.some((p) => p.value === mode) ? mode : "custom"}
        onChange={(e) => setHistoryMode(e.target.value)}
        title="View live data or pick a historical window"
      >
        {PRESETS.map((p) => (
          <option key={p.value} value={p.value}>
            {p.label}
          </option>
        ))}
        <option value="custom">By Day…</option>
      </select>
      {(mode === "custom" || /^\d{4}-\d{2}-\d{2}$/.test(mode)) && (
        <select
          value={/^\d{4}-\d{2}-\d{2}$/.test(mode) ? mode : days[0] ?? ""}
          onChange={(e) => setHistoryMode(e.target.value)}
          title="Pick a recorded day"
        >
          {days.length === 0 && <option value="">no recorded days</option>}
          {days.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
