import type { CapabilityReadinessEntry } from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface CapabilityReadinessPanelProps {
  readiness: CapabilityReadinessEntry[];
}

export function CapabilityReadinessPanel({ readiness }: CapabilityReadinessPanelProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Capability Readiness</h2>
        <span className="counter">{readiness.length}</span>
      </div>
      <div className="dense-list">
        {readiness.length === 0 ? <p className="muted">No readiness entries.</p> : null}
        {readiness.map((entry) => (
          <article key={entry.capability_id} className="list-row">
            <div>
              <strong>{entry.capability_id}</strong>
              <p>{entry.reason}</p>
            </div>
            <div className="row-meta">
              <StatusBadge value={entry.status} />
              <span className="source-chip">{entry.primary_tool_id ?? entry.available_tools[0]?.tool_id ?? "no tool"}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
