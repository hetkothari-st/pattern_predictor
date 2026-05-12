import { useEffect, useMemo, useRef, useState } from "react";
import type { Time } from "lightweight-charts";
import { useStore } from "../state/store";
import { subscribeChartHandle } from "../state/chartHandle";
import { PatternMiniature } from "./PatternMiniature";

type Mood = "idle" | "scanning" | "thinking" | "found";

const MOOD_LABEL: Record<Mood, string> = {
  idle: "waiting for ticks",
  scanning: "scanning candles",
  thinking: "candidate forming",
  found: "pattern confirmed",
};
const MOOD_TAG: Record<Mood, string> = {
  idle: "Idle",
  scanning: "Scanning",
  thinking: "Forming",
  found: "Confirmed",
};

function readVar(name: string, fallback: string) {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

interface Pos {
  left: number;
  top: number;
}

function useFollowBar(ts: number | undefined, price: number): Pos | null {
  const [pos, setPos] = useState<Pos | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (ts === undefined) {
      setPos(null);
      return;
    }
    let cancelled = false;

    const compute = () => {
      const handle = (window as any).__chartHandle as
        | { chart: any; series: any }
        | undefined;
      if (!handle) return null;
      const x = handle.chart.timeScale().timeToCoordinate(ts as Time);
      const y = handle.series.priceToCoordinate(price);
      if (x == null || y == null) return null;
      return { left: x, top: y };
    };

    const tick = () => {
      if (cancelled) return;
      const next = compute();
      if (next) {
        setPos((prev) =>
          !prev || prev.left !== next.left || prev.top !== next.top ? next : prev
        );
      }
      rafRef.current = window.requestAnimationFrame(tick);
    };

    const unsub = subscribeChartHandle((handle) => {
      if (handle) {
        (window as any).__chartHandle = handle;
        tick();
      }
    });

    return () => {
      cancelled = true;
      unsub();
      if (rafRef.current != null) window.cancelAnimationFrame(rafRef.current);
    };
  }, [ts, price]);

  return pos;
}

export function RobotWidget() {
  const detections = useStore((s) => s.detections);
  const bars = useStore((s) => s.bars);

  const { mood, top } = useMemo(() => {
    const all = Object.values(detections);
    const completed = all.find((d) => d.status === "completed");
    if (completed) return { mood: "found" as Mood, top: completed };
    const forming = all
      .filter((d) => d.status === "forming")
      .sort((a, b) => b.confidence - a.confidence)[0];
    if (forming) return { mood: "thinking" as Mood, top: forming };
    if (bars.length > 0) return { mood: "scanning" as Mood, top: undefined };
    return { mood: "idle" as Mood, top: undefined };
  }, [detections, bars.length]);

  const [palette, setPalette] = useState({
    bull: "#26a69a",
    bear: "#ef5350",
    accent: "#2962ff",
    text: "#9aa0a6",
    bg: "#1e222d",
  });

  useEffect(() => {
    const update = () =>
      setPalette({
        bull: readVar("--bull", "#26a69a"),
        bear: readVar("--bear", "#ef5350"),
        accent: readVar("--accent", "#2962ff"),
        text: readVar("--text-3", "#9aa0a6"),
        bg: readVar("--bg-2", "#1e222d"),
      });
    update();
    const obs = new MutationObserver(update);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);

  const moodColor =
    mood === "found"
      ? palette.bull
      : mood === "thinking" || mood === "scanning"
        ? palette.accent
        : palette.text;

  const lastBar = bars[bars.length - 1];
  const target = useFollowBar(lastBar?.ts, lastBar?.high ?? lastBar?.close ?? 0);

  const cardStyle: React.CSSProperties = target
    ? {
        position: "absolute",
        left: Math.max(12, target.left - 320),
        top: Math.max(12, target.top - 36),
        transition:
          "left 0.45s cubic-bezier(0.22, 1, 0.36, 1), top 0.45s cubic-bezier(0.22, 1, 0.36, 1)",
        zIndex: 24,
        pointerEvents: "auto",
      }
    : { position: "absolute", right: 84, bottom: 14, zIndex: 24, pointerEvents: "auto" };

  const robotStyle: React.CSSProperties = target
    ? {
        position: "absolute",
        left: target.left + 14,
        top: Math.max(8, target.top - 30),
        transition:
          "left 0.45s cubic-bezier(0.22, 1, 0.36, 1), top 0.45s cubic-bezier(0.22, 1, 0.36, 1)",
        zIndex: 25,
        pointerEvents: "none",
      }
    : { position: "absolute", right: 14, bottom: 14, zIndex: 25, pointerEvents: "none" };

  return (
    <>
      {top && (
        <div className={`robot-card ${mood}`} style={cardStyle}>
          <PatternMiniature pattern={top.pattern} direction={top.direction} size={52} />
          <div>
            <div className="robot-card-tag">{MOOD_TAG[mood]}</div>
            <div className="robot-card-pat">{top.pattern.replaceAll("_", " ")}</div>
            <div className="robot-card-meta">
              {top.direction} · {(top.confidence * 100).toFixed(0)}%
            </div>
          </div>
        </div>
      )}
      <Robot accent={moodColor} mood={mood} bg={palette.bg} text={palette.text} style={robotStyle} />
    </>
  );
}

function Robot({
  accent,
  mood,
  bg,
  text,
  style,
}: {
  accent: string;
  mood: Mood;
  bg: string;
  text: string;
  style: React.CSSProperties;
}) {
  return (
    <div title={MOOD_LABEL[mood]} style={style}>
      <svg viewBox="0 0 64 64" width="56" height="56">
        <line x1="32" y1="4" x2="32" y2="14" stroke={text} strokeWidth="1.4" />
        <circle cx="32" cy="4" r="2.6" fill={accent}>
          <animate attributeName="opacity" values="0.3;1;0.3" dur="1.4s" repeatCount="indefinite" />
        </circle>
        <rect
          x="10"
          y="14"
          width="44"
          height="34"
          rx="6"
          fill={bg}
          stroke={accent}
          strokeWidth="1.4"
        />
        <circle cx="23" cy="30" r="3.2" fill={accent}>
          <animate attributeName="r" values="2.8;3.4;2.8" dur="2.2s" repeatCount="indefinite" />
        </circle>
        <circle cx="41" cy="30" r="3.2" fill={accent}>
          <animate attributeName="r" values="2.8;3.4;2.8" dur="2.2s" repeatCount="indefinite" />
        </circle>
        <rect x="14" y="38" width="36" height="2" rx="1" fill={accent} opacity="0.35">
          <animate
            attributeName="x"
            values={mood === "idle" ? "14;14" : "14;46;14"}
            dur="2.4s"
            repeatCount="indefinite"
          />
          <animate
            attributeName="width"
            values={mood === "idle" ? "36;36" : "12;4;12"}
            dur="2.4s"
            repeatCount="indefinite"
          />
        </rect>
        <rect x="28" y="48" width="8" height="6" fill={bg} />
        <rect
          x="14"
          y="54"
          width="36"
          height="6"
          rx="2"
          fill={bg}
          stroke={accent}
          strokeWidth="1"
        />
      </svg>
    </div>
  );
}
