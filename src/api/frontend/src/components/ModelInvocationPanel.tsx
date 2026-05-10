import type { CapabilityReadinessEntry, PendingActionDetail } from "../api/types";

interface ModelInvocationPanelProps {
  readiness: CapabilityReadinessEntry[];
  pendingActionDetail: PendingActionDetail | null;
}

export function ModelInvocationPanel({ readiness, pendingActionDetail }: ModelInvocationPanelProps) {
  const candidateTools = pendingActionDetail?.candidates.map((candidate) => candidate.tool) ?? [];
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>模型调用</h2>
        <span className="counter">{candidateTools.length || readiness.length}</span>
      </div>
      {candidateTools.length ? (
        <div className="dense-list">
          {candidateTools.map((tool, index) => (
            <article key={`${tool.tool_id ?? "tool"}-${index}`} className="list-row">
              <div>
                <strong>{tool.tool_id ?? "未知工具"}</strong>
                <p>{tool.availability_hint}</p>
              </div>
              <div className="row-meta">
                <span className="source-chip">{tool.adapter_mode ?? "未知"}</span>
                <span className="source-chip">{tool.execution_mode ?? tool.provider ?? "默认"}</span>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="muted">加载等待中的任务后查看调用上下文。</p>
      )}
    </section>
  );
}
