import type { PendingActionDetail } from "../api/types";
import { CandidateComparison } from "./CandidateComparison";
import { DecisionForm } from "./DecisionForm";
import { JsonDisclosure } from "./JsonDisclosure";

interface PendingReviewWorkspaceProps {
  detail: PendingActionDetail | null;
  onDecisionSubmitted: () => void;
}

export function PendingReviewWorkspace({ detail, onDecisionSubmitted }: PendingReviewWorkspaceProps) {
  return (
    <section className="workspace-band review-workspace">
      <div className="review-main">
        <section className="panel review-context">
          <div className="panel-header">
            <h2>Runtime Context</h2>
            <span className="counter">{detail?.action_type ?? "idle"}</span>
          </div>
          {detail ? (
            <dl className="kv">
              <dt>Default</dt>
              <dd>{detail.default_suggestion ?? "none"}</dd>
              <dt>Reason</dt>
              <dd>{detail.workflow_action_reason ?? detail.explanation}</dd>
              <dt>Runtime state</dt>
              <dd><JsonDisclosure title="Runtime JSON" value={detail.runtime_state_summary} /></dd>
              <dt>Score</dt>
              <dd><JsonDisclosure title="Score JSON" value={detail.score_breakdown} /></dd>
              <dt>Evidence</dt>
              <dd>{detail.evidence_refs.length ? `${detail.evidence_refs.length} refs` : "not provided"}</dd>
            </dl>
          ) : (
            <p className="muted">Load a waiting task to inspect runtime context and recommendation evidence.</p>
          )}
        </section>
        <CandidateComparison detail={detail} />
      </div>
      <DecisionForm detail={detail} onSubmitted={onDecisionSubmitted} />
    </section>
  );
}
