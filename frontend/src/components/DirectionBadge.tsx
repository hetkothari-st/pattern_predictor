import { useStore } from "../state/store";

export function DirectionBadge() {
  const detections = useStore((s) => s.detections);
  const top = Object.values(detections).sort((a, b) => b.confidence - a.confidence)[0];

  if (!top) {
    return (
      <div className="badge">
        <div className="badge-icon">·</div>
        <div className="badge-body">
          <div className="badge-pat">No active pattern</div>
          <div className="badge-meta">watching tape</div>
        </div>
      </div>
    );
  }

  const cls = top.direction === "bullish" ? "bull" : "bear";
  const arrow = top.direction === "bullish" ? "▲" : "▼";

  return (
    <div className={`badge ${cls}`}>
      <div className="badge-icon">{arrow}</div>
      <div className="badge-body">
        <div className="badge-pat">{top.pattern.replaceAll("_", " ")}</div>
        <div className="badge-meta">
          <b>{(top.confidence * 100).toFixed(0)}%</b> · {top.status}
        </div>
      </div>
    </div>
  );
}
