import { useStore } from "../state/store";

export function DirectionBadge() {
  const detections = useStore((s) => s.detections);
  const top = Object.values(detections)
    .sort((a, b) => b.confidence - a.confidence)[0];
  if (!top) {
    return (
      <div style={badge("#30363d")}>
        <strong>No active pattern</strong>
        <span style={{ opacity: 0.7 }}>watching the tape</span>
      </div>
    );
  }
  const color = top.direction === "bullish" ? "#238636" : "#a40e26";
  return (
    <div style={badge(color)}>
      <strong>{top.direction.toUpperCase()}</strong>
      <span>
        {top.pattern.replaceAll("_", " ")} — {(top.confidence * 100).toFixed(0)}%{" "}
        ({top.status})
      </span>
    </div>
  );
}

function badge(bg: string): React.CSSProperties {
  return {
    background: bg,
    padding: "10px 14px",
    borderRadius: 8,
    display: "flex",
    flexDirection: "column",
    gap: 2,
    minWidth: 220,
  };
}
