import { useStore } from "../state/store";

export function EarlySignalsFeed() {
  const detections = useStore((s) => s.detections);
  const forming = Object.values(detections)
    .filter((d) => d.status === "forming")
    .sort((a, b) => b.confidence - a.confidence);
  return (
    <div style={{ padding: 12, overflow: "auto", flex: 1, borderTop: "1px solid #1f2937" }}>
      <div style={{ fontSize: 11, opacity: 0.6, marginBottom: 6, letterSpacing: 0.5 }}>
        WATCHING FOR
      </div>
      {forming.length === 0 && (
        <div style={{ opacity: 0.5, fontSize: 13 }}>Nothing pre-pattern right now.</div>
      )}
      {forming.map((d) => (
        <div
          key={d.id}
          style={{
            padding: "6px 8px",
            marginBottom: 4,
            background: "#161b22",
            borderLeft: `3px solid ${d.direction === "bullish" ? "#3fb950" : "#f85149"}`,
            borderRadius: 4,
            fontSize: 13,
          }}
        >
          <div>
            {d.pattern.replaceAll("_", " ")} —{" "}
            <strong>{(d.confidence * 100).toFixed(0)}%</strong>
          </div>
          {d.notes && <div style={{ opacity: 0.6, fontSize: 12 }}>{d.notes}</div>}
        </div>
      ))}
    </div>
  );
}
