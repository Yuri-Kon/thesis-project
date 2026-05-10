import type { PendingActionDetail } from "../api/types";
import { identifierLabel } from "../utils/displayText";

interface CandidateComparisonProps {
  detail: PendingActionDetail | null;
}

export function CandidateComparison({ detail }: CandidateComparisonProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>候选方案对比</h2>
        <span className="counter">{detail?.candidates.length ?? 0}</span>
      </div>
      {detail ? <p className="muted">{detail.recommendation_summary}</p> : null}
      {detail?.workflow_action_reason ? (
        <div className="reason-strip">
          <strong>推荐意见</strong>
          <span>{detail.workflow_action_reason}</span>
        </div>
      ) : null}
      <div className="candidate-grid">
        {!detail ? <p className="muted">未选择待处理操作。</p> : null}
        {detail?.candidates.map((candidate) => (
          <article key={candidate.candidate_id} className="candidate-card">
            <header>
              <strong>{candidate.candidate_id}</strong>
              <div className="row-meta">
                {candidate.is_default ? <span className="pill">默认</span> : null}
                <span className="source-chip">{identifierLabel(candidate.risk_level ?? "风险未知")}</span>
                <span className="source-chip">{candidate.cost_estimate ?? "成本未知"}</span>
              </div>
            </header>
            <p>{candidate.summary}</p>
            <dl className="kv compact-kv">
              <dt>影响</dt>
              <dd>{candidate.expected_effect ?? "未提供"}</dd>
              <dt>受影响步骤</dt>
              <dd>{candidate.affected_steps.length ? candidate.affected_steps.join(", ") : "无"}</dd>
              <dt>工具</dt>
              <dd>{candidate.tool.tool_id ?? "未知"}</dd>
            </dl>
            <details className="inline-details">
              <summary>决策证据</summary>
              <dl className="kv compact-kv">
                <dt>恢复语义</dt>
                <dd>{candidate.recovery_semantics ?? "标准决策流程"}</dd>
                <dt>证据</dt>
                <dd>{candidate.evidence_refs.length ? `${candidate.evidence_refs.length} 条引用` : candidate.workflow_action_reason ?? "未提供"}</dd>
                <dt>原因</dt>
                <dd>{candidate.recommendation_reason}</dd>
              </dl>
            </details>
          </article>
        ))}
      </div>
    </section>
  );
}
