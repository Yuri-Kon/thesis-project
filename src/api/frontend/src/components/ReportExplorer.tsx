import type { TaskRecord, TaskReportDetail } from "../api/types";
import { JsonDisclosure } from "./JsonDisclosure";

interface ReportExplorerProps {
  task: TaskRecord | null;
  report: TaskReportDetail | null;
}

export function ReportExplorer({ task, report }: ReportExplorerProps) {
  const designResult = task?.design_result;
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
          <dt>Artifacts</dt>
          <dd><JsonDisclosure title="Artifact metadata" value={task.metadata?.confirmed_task_spec ?? task.metadata} /></dd>
        </dl>
      ) : null}
    </section>
  );
}
