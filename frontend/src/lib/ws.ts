import type { WSMessage } from "../types";
import { useStore } from "../state/store";

export function connectStream(symbol: string, tf: string): () => void {
  const url = `ws://${window.location.host}/ws/stream?symbol=${encodeURIComponent(symbol)}&tf=${encodeURIComponent(tf)}`;
  let ws: WebSocket | null = null;
  let stopped = false;
  let backoff = 500;

  const open = () => {
    ws = new WebSocket(url);
    ws.onopen = () => {
      backoff = 500;
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as WSMessage;
        const s = useStore.getState();
        if (msg.type === "snapshot") s.applySnapshot(msg.payload.bars, msg.payload.detections, msg.payload.guidance);
        else if (msg.type === "bar") s.applyBar(msg.payload);
        else if (msg.type === "detection") s.applyDetection(msg.payload);
        else if (msg.type === "guidance") s.applyGuidance(msg.payload);
      } catch {
        /* ignore parse errors */
      }
    };
    ws.onclose = () => {
      if (stopped) return;
      setTimeout(open, backoff);
      backoff = Math.min(backoff * 2, 10_000);
    };
    ws.onerror = () => ws?.close();
  };

  open();
  return () => {
    stopped = true;
    ws?.close();
  };
}
