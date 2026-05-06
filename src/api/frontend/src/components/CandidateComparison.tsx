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
      {detail?.workflow_action_reason ? (
        <div className="reason-strip">
          <strong>Recommendation</strong>
          <span>{detail.workflow_action_reason}</span>
        </div>
      ) : null}
      <div className="candidate-grid">
        {!detail ? <p className="muted">No pending action selected.</p> : null}
        {detail?.candidates.map((candidate) => (
          <article key={candidate.candidate_id} className="candidate-card">
            <header>
              <strong>{candidate.candidate_id}</strong>
              <div className="row-meta">
                {candidate.is_default ? <span className="pill">default</span> : null}
                <span className="source-chip">{candidate.risk_level ?? "risk unknown"}</span>
                <span className="source-chip">{candidate.cost_estimate ?? "cost unknown"}</span>
              </div>
            </header>
            <p>{candidate.summary}</p>
            <dl className="kv compact-kv">
              <dt>Effect</dt>
              <dd>{candidate.expected_effect ?? "not provided"}</dd>
              <dt>Affected steps</dt>
              <dd>{candidate.affected_steps.length ? candidate.affected_steps.join(", ") : "none"}</dd>
              <dt>Tool</dt>
              <dd>{candidate.tool.tool_id ?? "unknown"}</dd>
            </dl>
            <details className="inline-details">
              <summary>Decision evidence</summary>
              <dl className="kv compact-kv">
                <dt>Recovery</dt>
                <dd>{candidate.recovery_semantics ?? "standard decision flow"}</dd>
                <dt>Evidence</dt>
                <dd>{candidate.evidence_refs.length ? `${candidate.evidence_refs.length} refs` : candidate.workflow_action_reason ?? "not provided"}</dd>
                <dt>Reason</dt>
                <dd>{candidate.recommendation_reason}</dd>
              </dl>
            </details>
          </article>
        ))}
      </div>
    </section>
  );
}
