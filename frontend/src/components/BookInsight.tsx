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
  { key: "formation", label: "How it forms" },
  { key: "causes", label: "Why it happens" },
  { key: "next_steps", label: "What to do" },
  { key: "outcome", label: "What follows" },
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

  if (!top) return null;
  const facets = insight?.facets ?? {};
  const anyText = FACET_LABELS.some((f) => facets[f.key]);

  return (
    <section className="aside-section">
      <div className="dept-line">
        <span className="dept">§ IV &middot; From the Book</span>
      </div>
      <div style={{ padding: "4px 16px 14px" }}>
        {loading && (
          <div className="empty" style={{ padding: "8px 0" }}>
            Consulting Bulkowski…
          </div>
        )}
        {!loading && !anyText && (
          <div className="empty" style={{ padding: "8px 0" }}>
            No book passages indexed for <em>{top.pattern.replaceAll("_", " ")}</em>.
            Run <span className="mono-num">ingest_book --chroma</span> to populate.
          </div>
        )}
        {!loading &&
          anyText &&
          FACET_LABELS.map(({ key, label }) =>
            facets[key] ? (
              <div key={key} style={{ marginBottom: 12 }}>
                <div
                  style={{
                    fontFamily: "var(--mono)",
                    fontSize: 9,
                    letterSpacing: "0.18em",
                    textTransform: "uppercase",
                    color: "var(--bone-faint)",
                    marginBottom: 4,
                  }}
                >
                  {label}
                </div>
                <div
                  style={{
                    fontFamily: "var(--accent)",
                    fontSize: 13,
                    lineHeight: 1.5,
                    color: "var(--bone-dim)",
                  }}
                >
                  {facets[key]}
                </div>
              </div>
            ) : null
          )}
      </div>
    </section>
  );
}
