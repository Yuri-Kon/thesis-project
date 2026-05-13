import type { TaskRecord, TaskReportDetail } from "../api/types";
import { JsonDisclosure } from "./JsonDisclosure";

interface ReportExplorerProps {
  task: TaskRecord | null;
  report: TaskReportDetail | null;
}

export function ReportExplorer({ task, report }: ReportExplorerProps) {
  const designResult = task?.design_result;
  const objectiveScoring = report?.objective_scoring ?? designResult?.metadata?.objective_scoring;
  const posteriorScore = isRecord(objectiveScoring) && isRecord(objectiveScoring.posterior_score)
    ? objectiveScoring.posterior_score
    : null;
  const topK = isRecord(objectiveScoring) && Array.isArray(objectiveScoring.top_k)
    ? objectiveScoring.top_k.filter(isRecord)
    : [];
  const warnings = isRecord(objectiveScoring) && Array.isArray(objectiveScoring.warnings)
    ? objectiveScoring.warnings.filter((item): item is string => typeof item === "string")
    : [];
  const evidenceRefs = isRecord(objectiveScoring) && Array.isArray(objectiveScoring.evidence_refs)
    ? objectiveScoring.evidence_refs.filter(isRecord)
    : [];
  const structureSimilarity = report?.structure_similarity ?? designResult?.metadata?.structure_similarity;
  const topStructureHit = isRecord(structureSimilarity) && isRecord(structureSimilarity.top_hit) ? structureSimilarity.top_hit : null;
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>报告浏览器</h2>
      </div>
      {!task ? <p className="muted">加载任务后查看报告和产物。</p> : null}
      {task ? (
        <dl className="kv">
          <dt>报告路径</dt>
          <dd>{report?.report_path ?? designResult?.report_path ?? "不可用"}</dd>
          <dt>评分</dt>
          <dd><JsonDisclosure title="评分 JSON" value={report?.scores ?? designResult?.scores} /></dd>
          <dt>目标评分</dt>
          <dd>
            {isRecord(objectiveScoring) ? (
              <div className="report-summary">
                <span>{formatNumber(objectiveScoring.objective_score ?? posteriorScore?.aggregate_score)}</span>
                <span>{String(posteriorScore?.evidence_status ?? "证据不可用")}</span>
                <span>{warnings.length} 个警告</span>
                {topK.length ? (
                  <table className="compact-table">
                    <thead>
                      <tr>
                        <th>候选方案</th>
                        <th>评分</th>
                        <th>证据</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topK.slice(0, 5).map((row) => {
                        const rowPosterior = isRecord(row.posterior_score) ? row.posterior_score : {};
                        return (
                          <tr key={String(row.candidate_id ?? row.id ?? row.top_k_rank)}>
                            <td>{String(row.candidate_id ?? row.id ?? "-")}</td>
                            <td>{formatNumber(row.objective_score)}</td>
                            <td>{String(rowPosterior.evidence_status ?? "-")}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ) : null}
                {evidenceRefs.length ? <JsonDisclosure title="证据引用" value={evidenceRefs} /> : null}
                {warnings.length ? <JsonDisclosure title="警告" value={warnings} /> : null}
                <JsonDisclosure title="目标评分 JSON" value={objectiveScoring} />
              </div>
            ) : (
              "不可用"
            )}
          </dd>
          <dt>结构相似性</dt>
          <dd>
            {isRecord(structureSimilarity) ? (
              <div className="report-summary">
                <span>{String(structureSimilarity.hit_count ?? 0)} 个命中</span>
                <span>{String(topStructureHit?.hit_id ?? topStructureHit?.target_id ?? "无最佳命中")}</span>
                <JsonDisclosure title="结构相似性 JSON" value={structureSimilarity} />
              </div>
            ) : (
              "不可用"
            )}
          </dd>
          <dt>产物</dt>
          <dd><JsonDisclosure title="产物元数据" value={task.metadata?.confirmed_task_spec ?? task.metadata} /></dd>
        </dl>
      ) : null}
    </section>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatNumber(value: unknown): string {
  return typeof value === "number" ? value.toFixed(3) : String(value ?? "-");
}
