export interface Bar {
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

export interface AnchorPoint {
  ts: number;
  price: number;
  label: string;
}

export interface Detection {
  id: string;
  pattern: string;
  direction: "bullish" | "bearish";
  status: "forming" | "completed";
  confidence: number;
  source: "rule" | "ml" | "fused";
  start_ts: number;
  end_ts: number;
  anchors: AnchorPoint[];
  notes: string;
}

export interface Guidance {
  pattern: string;
  summary: string;
  entry_rule: string;
  target_rule: string;
  stop_rule: string;
  success_rate: number; // 0..1
  avg_move: number;     // percent, e.g. 0.18
  throwback_pct: number;
  source_quote: string;
}

export type WSMessage =
  | { type: "snapshot"; payload: { bars: Bar[] } }
  | { type: "bar"; payload: Bar }
  | { type: "detection"; payload: Detection }
  | { type: "guidance"; payload: Guidance };
