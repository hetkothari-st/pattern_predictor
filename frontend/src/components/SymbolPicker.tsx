import { useEffect, useState } from "react";
import { useStore } from "../state/store";

interface SymbolEntry {
  symbol: string;
  label: string;
  group: string;
}

export function SymbolPicker() {
  const symbol = useStore((s) => s.symbol);
  const tf = useStore((s) => s.tf);
  const setSymbolTf = useStore((s) => s.setSymbolTf);
  const [items, setItems] = useState<SymbolEntry[]>([]);

  useEffect(() => {
    fetch("/api/symbols")
      .then((r) => r.json())
      .then((j) => setItems(j.items ?? []))
      .catch(() => {});
  }, []);

  const groups = Array.from(new Set(items.map((i) => i.group)));

  return (
    <div style={{ display: "flex", gap: 6 }}>
      <select
        value={symbol}
        onChange={(e) => setSymbolTf(e.target.value, tf)}
        style={{ minWidth: 150 }}
      >
        {items.length === 0 && <option value={symbol}>{symbol}</option>}
        {groups.map((g) => (
          <optgroup key={g} label={g}>
            {items
              .filter((i) => i.group === g)
              .map((i) => (
                <option key={i.symbol} value={i.symbol}>
                  {i.label}
                </option>
              ))}
          </optgroup>
        ))}
      </select>
      <select value={tf} onChange={(e) => setSymbolTf(symbol, e.target.value)}>
        {["1m", "5m", "15m", "1h", "4h", "1d"].map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </select>
    </div>
  );
}
