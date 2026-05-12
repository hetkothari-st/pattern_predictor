import { useEffect, useState } from "react";

interface DriftEntry {
  baseline_precision: number;
  baseline_n: number;
  recent_precision: number;
  recent_n: number;
  delta: number;
  drift: boolean;
}

interface DriftReport {
  patterns: Record<string, DriftEntry>;
  drift_count: number;
  threshold: number;
  recent_n: number;
}

export function DriftPanel() {
  const [report, setReport] = useState<DriftReport | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetch("/api/drift?recent_n=50&threshold=0.1")
        .then((r) => r.json())
        .then((j) => {
          if (!cancelled) setReport(j);
        })
        .catch(() => {});
    load();
    const id = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (!report || Object.keys(report.patterns).length === 0) {
    return (
      <div className="empty">
        Not enough scored predictions yet. Drift report needs a history of completed patterns.
      </div>
    );
  }

  const rows = Object.entries(report.patterns).sort((a, b) => a[1].delta - b[1].delta);

  return (
    <div className="drift">
      <div className="drift-summary">
        {report.drift_count > 0 ? (
          <span className="drift-alert">
            {report.drift_count} pattern{report.drift_count === 1 ? "" : "s"} drifting
          </span>
        ) : (
          <span className="drift-ok">all patterns within threshold</span>
        )}
        <span className="drift-meta">
          window={report.recent_n} · threshold={(report.threshold * 100).toFixed(0)}%
        </span>
      </div>
      <table className="drift-table">
        <thead>
          <tr>
            <th>pattern</th>
            <th>base</th>
            <th>recent</th>
            <th>Δ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([pat, e]) => (
            <tr key={pat} className={e.drift ? "drift-row" : ""}>
              <td>{pat.replaceAll("_", " ")}</td>
              <td>{(e.baseline_precision * 100).toFixed(0)}%</td>
              <td>{(e.recent_precision * 100).toFixed(0)}%</td>
              <td className={e.delta < 0 ? "neg" : "pos"}>
                {e.delta >= 0 ? "+" : ""}
                {(e.delta * 100).toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
