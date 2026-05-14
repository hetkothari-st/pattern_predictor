import { create } from "zustand";
import type { Bar, Detection, Guidance } from "../types";

interface StoreState {
  symbol: string;
  tf: string;
  bars: Bar[];
  detections: Record<string, Detection>;
  guidance: Record<string, Guidance>;
  // "live" = follow the WS stream; anything else = static historical view
  // (see HistoryPicker for valid values: "today", "1d", "7d", ..., "YYYY-MM-DD").
  historyMode: string;
  setSymbolTf: (symbol: string, tf: string) => void;
  setHistoryMode: (mode: string) => void;
  applySnapshot: (bars: Bar[], detections?: Detection[], guidance?: Guidance[]) => void;
  applyBar: (b: Bar) => void;
  applyDetection: (d: Detection) => void;
  applyGuidance: (g: Guidance) => void;
}

export const useStore = create<StoreState>((set) => ({
  symbol: "NIFTY50",
  tf: "1m",
  bars: [],
  detections: {},
  guidance: {},
  historyMode: "live",
  setSymbolTf: (symbol, tf) =>
    set({ symbol, tf, bars: [], detections: {}, guidance: {}, historyMode: "live" }),
  setHistoryMode: (mode) => set({ historyMode: mode, bars: [], detections: {}, guidance: {} }),
  applySnapshot: (bars, detections, guidance) =>
    set({
      bars,
      detections: detections
        ? Object.fromEntries(detections.map((d) => [d.id, d]))
        : {},
      guidance: guidance
        ? Object.fromEntries(guidance.map((g) => [g.pattern, g]))
        : {},
    }),
  applyBar: (b) =>
    set((s) => {
      const bars = s.bars.slice();
      const last = bars[bars.length - 1];
      if (last && last.ts === b.ts) {
        bars[bars.length - 1] = b;
      } else {
        bars.push(b);
      }
      return { bars };
    }),
  applyDetection: (d) => set((s) => ({ detections: { ...s.detections, [d.id]: d } })),
  applyGuidance: (g) => set((s) => ({ guidance: { ...s.guidance, [g.pattern]: g } })),
}));
