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

const VERDICT_CLS: Record<string, string> = {
  confirmed: "bull",
  weak: "neutral",
  contradicted: "bear",
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

  if (!top) {
    return <div className="empty">No pattern to critique yet.</div>;
  }
  if (loading) {
    return <div className="empty">Consulting critic…</div>;
  }
  if (!critique || critique.available === false) {
    return <div className="empty">{critique?.reason ?? "Critic not available."}</div>;
  }

  const verdict = critique.verdict ?? "weak";
  const vCls = VERDICT_CLS[verdict] ?? "neutral";

  return (
    <div className="critic">
      <header className="critic-head">
        <span className={`critic-stamp ${vCls}`}>{verdict}</span>
        {critique.confidence_adjustment !== undefined && (
          <span className="critic-adj">×{critique.confidence_adjustment.toFixed(2)}</span>
        )}
        {critique.enabled === false && <span className="critic-offline">offline</span>}
      </header>

      {critique.reasoning && <p className="critic-reason">{critique.reasoning}</p>}

      {critique.suggested_action && (
        <div className="critic-block">
          <span className="critic-label">Suggested Action</span>
          <span className="critic-action">{critique.suggested_action}</span>
        </div>
      )}

      {critique.risks && critique.risks.length > 0 && (
        <div className="critic-block">
          <span className="critic-label">Risks</span>
          <ul className="critic-risks">
            {critique.risks.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
