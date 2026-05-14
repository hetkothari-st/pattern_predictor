import { useEffect, useMemo, useRef, useState } from "react";
import type { Time } from "lightweight-charts";
import { useStore } from "../state/store";
import { subscribeChartHandle } from "../state/chartHandle";
import { PatternMiniature } from "./PatternMiniature";
import type { Detection, Guidance } from "../types";

type Mood = "idle" | "scanning" | "thinking" | "found";

const MOOD_LABEL: Record<Mood, string> = {
  idle: "waiting for ticks",
  scanning: "scanning candles",
  thinking: "candidate forming",
  found: "pattern confirmed",
};

function readVar(name: string, fallback: string) {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

interface Pos { left: number; top: number; }

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
  const guidanceMap = useStore((s) => s.guidance);
  const bars = useStore((s) => s.bars);

  const { mood, top } = useMemo(() => {
    const all = Object.values(detections);
    const completed = all
      .filter((d) => d.status === "completed")
      .sort((a, b) => b.end_ts - a.end_ts)[0];
    if (completed) return { mood: "found" as Mood, top: completed };
    const forming = all
      .filter((d) => d.status === "forming" && d.confidence >= 0.5)
      .sort((a, b) => b.confidence - a.confidence)[0];
    if (forming) return { mood: "thinking" as Mood, top: forming };
    if (bars.length > 0) return { mood: "scanning" as Mood, top: undefined };
    return { mood: "idle" as Mood, top: undefined };
  }, [detections, bars.length]);

  const [palette, setPalette] = useState({
    bull: "#1ad17d",
    bear: "#ff3b4d",
    accent: "#4f8cff",
    text: "#a7abb2",
    bg: "#14181f",
  });

  useEffect(() => {
    const update = () =>
      setPalette({
        bull: readVar("--bull", "#1ad17d"),
        bear: readVar("--bear", "#ff3b4d"),
        accent: readVar("--accent", "#4f8cff"),
        text: readVar("--text-3", "#a7abb2"),
        bg: readVar("--bg-2", "#14181f"),
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

  const cardWidth = mood === "found" ? 360 : 280;
  const cardYOffset = mood === "found" ? 300 : 150;
  const cardStyle: React.CSSProperties = target
    ? {
        position: "absolute",
        left: Math.max(12, target.left - cardWidth - 16),
        top: Math.max(12, target.top - cardYOffset),
        transition:
          "left 0.35s cubic-bezier(0.22, 1, 0.36, 1), top 0.35s cubic-bezier(0.22, 1, 0.36, 1)",
        zIndex: 24,
        pointerEvents: "auto",
        width: cardWidth,
      }
    : {
        position: "absolute",
        right: 16,
        top: 16,
        zIndex: 24,
        pointerEvents: "auto",
        width: cardWidth,
      };

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
      {mood === "thinking" && top && <ThinkingCard detection={top} style={cardStyle} />}
      {mood === "found" && top && (
        <ConfirmedCard detection={top} guidance={guidanceMap[top.pattern]} style={cardStyle} />
      )}
      <Robot
        accent={moodColor}
        mood={mood}
        bg={palette.bg}
        text={palette.text}
        style={robotStyle}
      />
    </>
  );
}

function ThinkingCard({ detection, style }: { detection: Detection; style: React.CSSProperties }) {
  return (
    <div className="thinking-card" style={style}>
      <div className="thinking-head">
        <span className="thinking-tag">
          Thinking
          <span className="thinking-dots">
            <span />
            <span />
            <span />
          </span>
        </span>
        <span className="thinking-conf">{(detection.confidence * 100).toFixed(0)}%</span>
      </div>
      <div className="thinking-body">
        <PatternMiniature
          pattern={detection.pattern}
          direction={detection.direction}
          size={72}
        />
        <div className="thinking-meta">
          <div className="thinking-label">Possible pattern</div>
          <div className="thinking-name">{detection.pattern.replaceAll("_", " ")}</div>
          <div className={`thinking-dir ${detection.direction}`}>
            {detection.direction === "bullish" ? "▲ bullish bias" : "▼ bearish bias"}
          </div>
        </div>
      </div>
    </div>
  );
}

function ConfirmedCard({
  detection,
  guidance,
  style,
}: {
  detection: Detection;
  guidance?: Guidance;
  style: React.CSSProperties;
}) {
  const isBull = detection.direction === "bullish";
  const action = isBull ? "BUY" : "SELL";
  const dirCls = isBull ? "bull" : "bear";

  return (
    <div className={`confirmed-card ${dirCls}`} style={style}>
      <header className="confirmed-head">
        <span className="confirmed-tag">
          <span className="confirmed-check">✓</span>
          Pattern Confirmed
        </span>
        <span className="confirmed-conf">{(detection.confidence * 100).toFixed(0)}%</span>
      </header>

      <div className="confirmed-name-row">
        <PatternMiniature
          pattern={detection.pattern}
          direction={detection.direction}
          size={56}
        />
        <div>
          <div className="confirmed-name">{detection.pattern.replaceAll("_", " ")}</div>
          <div className={`confirmed-dir ${dirCls}`}>
            {isBull ? "Bullish formation" : "Bearish formation"}
          </div>
        </div>
        <span className={`action-chip ${dirCls}`}>{action}</span>
      </div>

      {guidance && (
        <>
          <div className="confirmed-bullets">
            <BulletRow label="Entry"  text={guidance.entry_rule} />
            <BulletRow label="Target" text={guidance.target_rule} accent />
            <BulletRow label="Stop"   text={guidance.stop_rule} danger />
          </div>

          <footer className="confirmed-stats">
            <Stat n={`${(guidance.success_rate * 100).toFixed(0)}%`} label="success" />
            <Stat n={`${(guidance.avg_move * 100).toFixed(0)}%`} label="avg move" />
            <Stat n={`${(guidance.throwback_pct * 100).toFixed(0)}%`} label="throwback" />
          </footer>
        </>
      )}
      {!guidance && (
        <div className="confirmed-no-guide">
          Reference data unavailable. Run book-ingest to enable next-step guidance.
        </div>
      )}
    </div>
  );
}

function BulletRow({
  label,
  text,
  accent,
  danger,
}: {
  label: string;
  text: string;
  accent?: boolean;
  danger?: boolean;
}) {
  return (
    <div className="bullet">
      <span className={`bullet-dot ${accent ? "accent" : danger ? "danger" : ""}`} />
      <span className="bullet-label">{label}</span>
      <span className="bullet-text">{text}</span>
    </div>
  );
}

function Stat({ n, label }: { n: string; label: string }) {
  return (
    <div className="cstat">
      <span className="cstat-n">{n}</span>
      <span className="cstat-l">{label}</span>
    </div>
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
