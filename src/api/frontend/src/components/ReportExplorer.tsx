import type { TaskRecord, TaskReportDetail } from "../api/types";

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
          <dd><pre>{JSON.stringify(report?.scores ?? designResult?.scores ?? {}, null, 2)}</pre></dd>
          <dt>Artifacts</dt>
          <dd><pre>{JSON.stringify(task.metadata?.confirmed_task_spec ?? task.metadata ?? {}, null, 2)}</pre></dd>
        </dl>
      ) : null}
    </section>
  );
}
