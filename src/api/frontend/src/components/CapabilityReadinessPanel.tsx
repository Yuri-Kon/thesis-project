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
        <h2>能力就绪状态</h2>
        <div className="row-meta">
          {blockedCount ? <span className="source-chip danger">{blockedCount} 个阻塞</span> : null}
          {degradedCount ? <span className="source-chip warning">{degradedCount} 个降级</span> : null}
          <span className="counter">{readiness.length}</span>
        </div>
      </div>
      <div className="readiness-list">
        {readiness.length === 0 ? <p className="muted">暂无能力就绪记录。</p> : null}
        {readiness.map((entry) => (
          <article key={entry.capability_id} className="readiness-row">
            <div className="readiness-copy">
              <strong>{entry.capability_id}</strong>
              <p>{entry.reason}</p>
            </div>
            <div className="readiness-meta">
              <StatusBadge value={entry.status} />
              <span className="source-chip">{entry.primary_tool_id ?? entry.available_tools[0]?.tool_id ?? "无工具"}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
