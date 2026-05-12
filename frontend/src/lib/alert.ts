import type { Detection } from "../types";

const seenCompletedIds = new Set<string>();
let audioCtx: AudioContext | null = null;
let permissionAsked = false;

function getCtx(): AudioContext | null {
  if (audioCtx) return audioCtx;
  const Ctor =
    (window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext }).AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  audioCtx = new Ctor();
  return audioCtx;
}

function beep(direction: "bullish" | "bearish") {
  const ctx = getCtx();
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.value = direction === "bullish" ? 880 : 440;
  gain.gain.setValueAtTime(0, ctx.currentTime);
  gain.gain.linearRampToValueAtTime(0.18, ctx.currentTime + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45);
  osc.connect(gain).connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.5);
}

function notify(symbol: string, d: Detection) {
  if (typeof Notification === "undefined") return;
  if (Notification.permission === "granted") {
    new Notification(`${symbol}: ${d.pattern.replaceAll("_", " ")}`, {
      body: `${d.direction.toUpperCase()} • ${(d.confidence * 100).toFixed(0)}% • ${d.status}`,
    });
  } else if (Notification.permission !== "denied" && !permissionAsked) {
    permissionAsked = true;
    Notification.requestPermission().catch(() => {});
  }
}

export function maybeAlert(symbol: string, d: Detection) {
  if (d.status !== "completed") return;
  if (seenCompletedIds.has(d.id)) return;
  seenCompletedIds.add(d.id);
  beep(d.direction);
  notify(symbol, d);
}

export function resetAlerts() {
  seenCompletedIds.clear();
}
