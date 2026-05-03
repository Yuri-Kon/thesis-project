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
        <h2>Report Explorer</h2>
      </div>
      {!task ? <p className="muted">Load a task to inspect reports and artifacts.</p> : null}
      {task ? (
        <dl className="kv">
          <dt>Report path</dt>
          <dd>{report?.report_path ?? designResult?.report_path ?? "not available"}</dd>
          <dt>Scores</dt>
          <dd><JsonDisclosure title="Score JSON" value={report?.scores ?? designResult?.scores} /></dd>
          <dt>Objective scoring</dt>
          <dd>
            {isRecord(objectiveScoring) ? (
              <div className="report-summary">
                <span>{formatNumber(objectiveScoring.objective_score ?? posteriorScore?.aggregate_score)}</span>
                <span>{String(posteriorScore?.evidence_status ?? "evidence n/a")}</span>
                <span>{warnings.length} warnings</span>
                {topK.length ? (
                  <table className="compact-table">
                    <thead>
                      <tr>
                        <th>Candidate</th>
                        <th>Score</th>
                        <th>Evidence</th>
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
                {evidenceRefs.length ? <JsonDisclosure title="Evidence refs" value={evidenceRefs} /> : null}
                {warnings.length ? <JsonDisclosure title="Warnings" value={warnings} /> : null}
                <JsonDisclosure title="Objective scoring JSON" value={objectiveScoring} />
              </div>
            ) : (
              "not available"
            )}
          </dd>
          <dt>Structure similarity</dt>
          <dd>
            {isRecord(structureSimilarity) ? (
              <div className="report-summary">
                <span>{String(structureSimilarity.hit_count ?? 0)} hits</span>
                <span>{String(topStructureHit?.hit_id ?? topStructureHit?.target_id ?? "no top hit")}</span>
                <JsonDisclosure title="Structure similarity JSON" value={structureSimilarity} />
              </div>
            ) : (
              "not available"
            )}
          </dd>
          <dt>Artifacts</dt>
          <dd><JsonDisclosure title="Artifact metadata" value={task.metadata?.confirmed_task_spec ?? task.metadata} /></dd>
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
