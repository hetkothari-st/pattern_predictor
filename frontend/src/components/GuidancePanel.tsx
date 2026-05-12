import { useStore } from "../state/store";
import type { Detection, Guidance } from "../types";

export function GuidancePanel() {
  const detections = useStore((s) => s.detections);
  const guidanceMap = useStore((s) => s.guidance);
  const completed = Object.values(detections)
    .filter((d: Detection) => d.status === "completed")
    .sort((a, b) => b.end_ts - a.end_ts);
  const top = completed[0];

  return (
    <div style={{ padding: 12, borderTop: "1px solid #30363d" }}>
      <h3 style={{ margin: "0 0 8px" }}>Guidance</h3>
      {!top && <div style={{ opacity: 0.6 }}>No completed pattern yet.</div>}
      {top && <Card detection={top} guidance={guidanceMap[top.pattern]} />}
    </div>
  );
}

function Card({ detection, guidance }: { detection: Detection; guidance?: Guidance }) {
  return (
    <div style={{ background: "#161b22", borderRadius: 6, padding: 10, fontSize: 13 }}>
      <div style={{ marginBottom: 6 }}>
        <strong>{detection.pattern.replaceAll("_", " ")}</strong>{" "}
        <span style={{ opacity: 0.7 }}>({detection.direction})</span>
      </div>
      {!guidance && (
        <div style={{ opacity: 0.6 }}>
          Bulkowski guidance not loaded. Run the book-ingest CLI to populate this card.
        </div>
      )}
      {guidance && (
        <>
          <Row label="Summary" value={guidance.summary} />
          <Row label="Entry" value={guidance.entry_rule} />
          <Row label="Target" value={guidance.target_rule} />
          <Row label="Stop" value={guidance.stop_rule} />
          <Row
            label="Historical success"
            value={`${(guidance.success_rate * 100).toFixed(0)}% (avg move ${(guidance.avg_move * 100).toFixed(0)}%, throwback ${(guidance.throwback_pct * 100).toFixed(0)}%)`}
            highlight
          />
          <div style={{ opacity: 0.55, fontStyle: "italic", marginTop: 6 }}>
            {guidance.source_quote}
          </div>
        </>
      )}
    </div>
  );
}

function Row({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div style={{ marginBottom: 4 }}>
      <span style={{ opacity: 0.7 }}>{label}: </span>
      <span style={highlight ? { color: "#d29922", fontWeight: 600 } : undefined}>{value}</span>
    </div>
  );
}
