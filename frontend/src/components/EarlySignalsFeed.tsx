import { useStore } from "../state/store";

export function EarlySignalsFeed() {
  const detections = useStore((s) => s.detections);
  const forming = Object.values(detections)
    .filter((d) => d.status === "forming")
    .sort((a, b) => b.confidence - a.confidence);

  if (forming.length === 0) {
    return <div className="empty">Nothing pre-pattern right now.</div>;
  }

  return (
    <>
      {forming.map((d) => (
        <div key={d.id} className={`signal ${d.direction === "bullish" ? "bull" : "bear"}`}>
          <div>
            <div className="signal-name">{d.pattern.replaceAll("_", " ")}</div>
            <div className="signal-meta">
              {d.direction} · forming · {d.source}
            </div>
          </div>
          <span className="signal-conf">{(d.confidence * 100).toFixed(0)}%</span>
          {d.notes && <div className="signal-note">{d.notes}</div>}
        </div>
      ))}
    </>
  );
}
