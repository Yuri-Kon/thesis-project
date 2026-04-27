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
        <h2>Model Invocation</h2>
        <span className="counter">{candidateTools.length || readiness.length}</span>
      </div>
      {candidateTools.length ? (
        <div className="dense-list">
          {candidateTools.map((tool, index) => (
            <article key={`${tool.tool_id ?? "tool"}-${index}`} className="list-row">
              <div>
                <strong>{tool.tool_id ?? "unknown tool"}</strong>
                <p>{tool.availability_hint}</p>
              </div>
              <span>{tool.adapter_mode ?? "unknown"}</span>
              <span>{tool.execution_mode ?? tool.provider ?? "default"}</span>
            </article>
          ))}
        </div>
      ) : (
        <p className="muted">Load a waiting task to inspect invocation context.</p>
      )}
    </section>
  );
}
