import { useStore } from "../state/store";
import type { Detection, Guidance } from "../types";

export function GuidancePanel() {
  const detections = useStore((s) => s.detections);
  const guidanceMap = useStore((s) => s.guidance);
  const completed = Object.values(detections)
    .filter((d: Detection) => d.status === "completed")
    .sort((a, b) => b.end_ts - a.end_ts);
  const top = completed[0];

  if (!top) return <div className="empty">No completed pattern in this session.</div>;
  return <Card detection={top} guidance={guidanceMap[top.pattern]} />;
}

function Card({ detection, guidance }: { detection: Detection; guidance?: Guidance }) {
  const dirCls = detection.direction === "bullish" ? "bull" : "bear";
  return (
    <article className="guide">
      <header className="guide-head">
        <div>
          <div className="guide-title">{detection.pattern.replaceAll("_", " ")}</div>
          <div className="guide-dir">Completed · {detection.direction}</div>
        </div>
        <span className={`guide-stamp ${dirCls}`}>{detection.direction}</span>
      </header>
      <div className="guide-body">
        {!guidance && (
          <div className="empty" style={{ padding: "8px 0" }}>
            Bulkowski guidance not loaded. Run the book-ingest CLI to populate this card.
          </div>
        )}
        {guidance && (
          <>
            <Row label="Summary" value={guidance.summary} />
            <Row label="Entry" value={guidance.entry_rule} />
            <Row label="Target" value={guidance.target_rule} />
            <Row label="Stop" value={guidance.stop_rule} />

            <div className="guide-stats">
              <div className="guide-stat accent">
                <span className="guide-stat-label">Success</span>
                <span className="guide-stat-val">
                  {(guidance.success_rate * 100).toFixed(0)}%
                </span>
              </div>
              <div className="guide-stat">
                <span className="guide-stat-label">Avg Move</span>
                <span className="guide-stat-val">
                  {(guidance.avg_move * 100).toFixed(0)}%
                </span>
              </div>
              <div className="guide-stat">
                <span className="guide-stat-label">Throwback</span>
                <span className="guide-stat-val">
                  {(guidance.throwback_pct * 100).toFixed(0)}%
                </span>
              </div>
            </div>

            <div className="guide-quote">{guidance.source_quote}</div>
          </>
        )}
      </div>
    </article>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="guide-row">
      <span className="guide-label">{label}</span>
      <span className="guide-value">{value}</span>
    </div>
  );
}
