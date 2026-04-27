import type { PendingActionDetail } from "../api/types";

interface CandidateComparisonProps {
  detail: PendingActionDetail | null;
}

export function CandidateComparison({ detail }: CandidateComparisonProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Candidate Comparison</h2>
        <span className="counter">{detail?.candidates.length ?? 0}</span>
      </div>
      {detail ? <p className="muted">{detail.recommendation_summary}</p> : null}
      <div className="candidate-grid">
        {!detail ? <p className="muted">No pending action selected.</p> : null}
        {detail?.candidates.map((candidate) => (
          <article key={candidate.candidate_id} className="candidate-card">
            <header>
              <strong>{candidate.candidate_id}</strong>
              {candidate.is_default ? <span className="pill">default</span> : null}
            </header>
            <p>{candidate.summary}</p>
            <dl>
              <dt>Risk</dt>
              <dd>{candidate.risk_level ?? "unknown"}</dd>
              <dt>Cost</dt>
              <dd>{candidate.cost_estimate ?? "unknown"}</dd>
              <dt>Tool</dt>
              <dd>{candidate.tool.tool_id ?? "unknown"}</dd>
              <dt>Reason</dt>
              <dd>{candidate.recommendation_reason}</dd>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}
