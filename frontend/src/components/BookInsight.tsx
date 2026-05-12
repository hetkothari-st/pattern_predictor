import { useEffect, useState } from "react";
import { useStore } from "../state/store";

interface Insight {
  pattern: string;
  facets: {
    formation?: string | null;
    causes?: string | null;
    next_steps?: string | null;
    outcome?: string | null;
  };
}

const FACET_LABELS: { key: keyof Insight["facets"]; label: string }[] = [
  { key: "formation", label: "Formation" },
  { key: "causes", label: "Causes" },
  { key: "next_steps", label: "Next Steps" },
  { key: "outcome", label: "Outcome" },
];

export function BookInsight() {
  const detections = useStore((s) => s.detections);
  const top = Object.values(detections)
    .filter((d) => d.status === "completed")
    .sort((a, b) => b.end_ts - a.end_ts)[0];

  const [insight, setInsight] = useState<Insight | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!top) {
      setInsight(null);
      return;
    }
    setLoading(true);
    let cancelled = false;
    fetch(`/api/insight?pattern=${encodeURIComponent(top.pattern)}`)
      .then((r) => r.json())
      .then((j) => {
        if (!cancelled) setInsight(j);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [top?.pattern]);

  if (!top) {
    return <div className="empty">No completed pattern yet. Reference will load on confirmation.</div>;
  }

  const facets = insight?.facets ?? {};
  const anyText = FACET_LABELS.some((f) => facets[f.key]);

  return (
    <div className="book">
      <div className="book-title">{top.pattern.replaceAll("_", " ")}</div>

      {loading && <div className="empty" style={{ padding: "8px 0" }}>Consulting reference…</div>}

      {!loading && !anyText && (
        <div className="empty" style={{ padding: "8px 0" }}>
          No book passages indexed for this pattern. Run <code>ingest_book --chroma</code> to populate.
        </div>
      )}

      {!loading &&
        anyText &&
        FACET_LABELS.map(({ key, label }, idx) =>
          facets[key] ? (
            <div key={key} className="book-facet">
              <div className="book-facet-head">
                <span className="book-facet-num">{String(idx + 1).padStart(2, "0")}</span>
                <span className="book-facet-label">{label}</span>
              </div>
              <div className="book-facet-body">{facets[key]}</div>
            </div>
          ) : null
        )}
    </div>
  );
}
