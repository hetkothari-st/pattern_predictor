import { useEffect, useState } from "react";

const SHAPES: Record<string, string> = {
  head_and_shoulders: "5,30 15,18 25,28 40,8 55,28 65,18 75,30",
  inverse_head_and_shoulders: "5,10 15,22 25,12 40,32 55,12 65,22 75,10",
  double_top: "5,30 20,12 35,28 50,12 75,30",
  double_bottom: "5,10 20,28 35,12 50,28 75,10",
  ascending_triangle: "5,12 75,12 5,32 70,15",
  descending_triangle: "5,28 75,28 5,8 70,25",
  symmetric_triangle: "5,8 70,18 5,32 70,22",
  rising_wedge: "5,28 70,12 5,32 70,18",
  falling_wedge: "5,12 70,28 5,8 70,22",
  bull_flag: "5,30 25,8 30,12 38,16 46,12 54,16 62,12 75,4",
  bear_flag: "5,10 25,32 30,28 38,24 46,28 54,24 62,28 75,36",
  bull_pennant: "5,30 25,8 30,18 50,16 65,17 75,8",
  bear_pennant: "5,10 25,32 30,22 50,24 65,23 75,32",
  cup_with_handle: "5,12 12,28 25,34 40,34 55,28 62,16 68,22 72,18 75,12",
};

function readVar(name: string, fallback: string) {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

export function PatternMiniature({
  pattern,
  direction,
  size = 64,
}: {
  pattern: string;
  direction: "bullish" | "bearish";
  size?: number;
}) {
  const [palette, setPalette] = useState({
    bull: "#26a69a",
    bear: "#ef5350",
    bg: "#1e222d",
    line: "#2a2e39",
  });

  useEffect(() => {
    const update = () =>
      setPalette({
        bull: readVar("--bull", "#26a69a"),
        bear: readVar("--bear", "#ef5350"),
        bg: readVar("--bg-1", "#1e222d"),
        line: readVar("--line-2", "#2a2e39"),
      });
    update();
    const obs = new MutationObserver(update);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);

  const points = SHAPES[pattern] ?? "";
  const stroke = direction === "bullish" ? palette.bull : palette.bear;
  const w = size;
  const h = (size * 40) / 80;
  return (
    <svg
      viewBox="0 0 80 40"
      width={w}
      height={h}
      style={{ display: "block", flexShrink: 0 }}
      aria-label={pattern}
    >
      <rect x="0" y="0" width="80" height="40" rx="3" fill={palette.bg} stroke={palette.line} />
      {points && (
        <polyline
          points={points}
          fill="none"
          stroke={stroke}
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
    </svg>
  );
}
