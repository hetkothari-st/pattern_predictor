import { useEffect, useState } from "react";
import { useStore } from "../state/store";

interface Critique {
  available: boolean;
  enabled?: boolean;
  reason?: string;
  pattern?: string;
  verdict?: "confirmed" | "weak" | "contradicted";
  confidence_adjustment?: number;
  reasoning?: string;
  suggested_action?: string;
  risks?: string[];
}

const VERDICT_COLOR: Record<string, string> = {
  confirmed: "var(--bull, #87a878)",
  weak: "var(--ochre, #c89b3c)",
  contradicted: "var(--bear, #b03a3a)",
};

export function CriticPanel() {
  const symbol = useStore((s) => s.symbol);
  const tf = useStore((s) => s.tf);
  const detections = useStore((s) => s.detections);
  const top = Object.values(detections)
    .filter((d) => d.status === "completed")
    .sort((a, b) => b.end_ts - a.end_ts)[0];

  const [critique, setCritique] = useState<Critique | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!top) {
      setCritique(null);
      return;
    }
    setLoading(true);
    let cancelled = false;
    fetch(
      `/api/critique?symbol=${encodeURIComponent(symbol)}&tf=${encodeURIComponent(tf)}&pattern=${encodeURIComponent(top.pattern)}`
    )
      .then((r) => r.json())
      .then((j) => {
        if (!cancelled) setCritique(j);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [top?.pattern, top?.end_ts, symbol, tf]);

  if (!top) return null;
  const verdict = critique?.verdict;
  const accent = verdict ? VERDICT_COLOR[verdict] : "var(--rule-strong, #3d352a)";

  return (
    <section className="aside-section">
      <div className="dept-line">
        <span className="dept">§ V &middot; Second Opinion</span>
      </div>
      <div style={{ padding: "4px 16px 14px" }}>
        {loading && (
          <div className="empty" style={{ padding: "8px 0" }}>
            Consulting the critic…
          </div>
        )}
        {!loading && critique && critique.available === false && (
          <div className="empty" style={{ padding: "8px 0" }}>
            {critique.reason ?? "Critic not available."}
          </div>
        )}
        {!loading && critique && critique.available && (
          <div
            style={{
              borderLeft: `2px solid ${accent}`,
              paddingLeft: 10,
              fontFamily: "var(--mono)",
            }}
          >
            <div
              style={{
                fontSize: 11,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: accent,
                marginBottom: 6,
                fontWeight: 600,
              }}
            >
              {verdict ?? "—"}
              {critique.confidence_adjustment !== undefined && (
                <span style={{ opacity: 0.6, marginLeft: 8 }}>
                  ×{critique.confidence_adjustment.toFixed(2)}
                </span>
              )}
              {critique.enabled === false && (
                <span style={{ marginLeft: 8, opacity: 0.5 }}>(offline)</span>
              )}
            </div>
            {critique.reasoning && (
              <div
                style={{
                  fontFamily: "var(--accent)",
                  fontSize: 13,
                  lineHeight: 1.5,
                  color: "var(--bone-dim, #a89c84)",
                  marginBottom: 10,
                }}
              >
                {critique.reasoning}
              </div>
            )}
            {critique.suggested_action && (
              <div style={{ marginBottom: 10 }}>
                <div
                  style={{
                    fontSize: 9,
                    letterSpacing: "0.18em",
                    textTransform: "uppercase",
                    color: "var(--bone-faint, #6b6253)",
                    marginBottom: 3,
                  }}
                >
                  Suggested action
                </div>
                <div style={{ fontSize: 12, color: "var(--bone, #ede4d2)" }}>
                  {critique.suggested_action}
                </div>
              </div>
            )}
            {critique.risks && critique.risks.length > 0 && (
              <div>
                <div
                  style={{
                    fontSize: 9,
                    letterSpacing: "0.18em",
                    textTransform: "uppercase",
                    color: "var(--bone-faint, #6b6253)",
                    marginBottom: 3,
                  }}
                >
                  Risks
                </div>
                <ul
                  style={{
                    margin: 0,
                    paddingLeft: 16,
                    fontSize: 12,
                    color: "var(--bone-dim, #a89c84)",
                  }}
                >
                  {critique.risks.map((r, i) => (
                    <li key={i} style={{ marginBottom: 2 }}>
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
