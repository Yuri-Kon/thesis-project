import type { PendingActionDetail } from "../api/types";
import { CandidateComparison } from "./CandidateComparison";
import { DecisionForm } from "./DecisionForm";
import { JsonDisclosure } from "./JsonDisclosure";
import { identifierLabel } from "../utils/displayText";

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
            <h2>运行时上下文</h2>
            <span className="counter">{identifierLabel(detail?.action_type ?? "idle")}</span>
          </div>
          {detail ? (
            <dl className="kv">
              <dt>默认建议</dt>
              <dd>{detail.default_suggestion ?? "无"}</dd>
              <dt>原因</dt>
              <dd>{detail.workflow_action_reason ?? detail.explanation}</dd>
              <dt>运行状态</dt>
              <dd><JsonDisclosure title="运行状态 JSON" value={detail.runtime_state_summary} /></dd>
              <dt>评分</dt>
              <dd><JsonDisclosure title="评分 JSON" value={detail.score_breakdown} /></dd>
              <dt>证据</dt>
              <dd>{detail.evidence_refs.length ? `${detail.evidence_refs.length} 条引用` : "未提供"}</dd>
            </dl>
          ) : (
            <p className="muted">加载等待中的任务后查看运行时上下文和推荐证据。</p>
          )}
        </section>
        <CandidateComparison detail={detail} />
      </div>
      <DecisionForm detail={detail} onSubmitted={onDecisionSubmitted} />
    </section>
  );
}
