import { useStore } from "../state/store";

// Drop low-confidence forming signals — random walks generate dozens of
// peak-triplet candidates that aren't real patterns.
const MIN_CONFIDENCE = 0.5;
const MAX_DISPLAY = 5;

export function EarlySignalsFeed() {
  const detections = useStore((s) => s.detections);
  const all = Object.values(detections).filter((d) => d.status === "forming");
  // Keep one entry per pattern (highest confidence) so the same pattern
  // doesn't repeat 6 times.
  const seen = new Set<string>();
  const filtered = all
    .filter((d) => d.confidence >= MIN_CONFIDENCE)
    .sort((a, b) => b.confidence - a.confidence)
    .filter((d) => {
      if (seen.has(d.pattern)) return false;
      seen.add(d.pattern);
      return true;
    })
    .slice(0, MAX_DISPLAY);

  if (filtered.length === 0) {
    const noisyCount = all.length;
    return (
      <div className="empty">
        {noisyCount > 0
          ? `Nothing high-confidence right now (${noisyCount} weak signals filtered).`
          : "Nothing pre-pattern right now."}
      </div>
    );
  }

  return (
    <>
      {filtered.map((d) => (
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
