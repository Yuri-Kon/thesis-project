import type { CapabilityReadinessEntry } from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface CapabilityReadinessPanelProps {
  readiness: CapabilityReadinessEntry[];
}

export function CapabilityReadinessPanel({ readiness }: CapabilityReadinessPanelProps) {
  const degradedCount = readiness.filter((entry) => entry.status === "degraded").length;
  const blockedCount = readiness.filter((entry) => entry.status === "blocked").length;

  return (
    <section className="panel capability-readiness-panel">
      <div className="panel-header">
        <h2>Capability Readiness</h2>
        <div className="row-meta">
          {blockedCount ? <span className="source-chip danger">{blockedCount} blocked</span> : null}
          {degradedCount ? <span className="source-chip warning">{degradedCount} degraded</span> : null}
          <span className="counter">{readiness.length}</span>
        </div>
      </div>
      <div className="readiness-list">
        {readiness.length === 0 ? <p className="muted">No readiness entries.</p> : null}
        {readiness.map((entry) => (
          <article key={entry.capability_id} className="readiness-row">
            <div className="readiness-copy">
              <strong>{entry.capability_id}</strong>
              <p>{entry.reason}</p>
            </div>
            <div className="readiness-meta">
              <StatusBadge value={entry.status} />
              <span className="source-chip">{entry.primary_tool_id ?? entry.available_tools[0]?.tool_id ?? "no tool"}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
