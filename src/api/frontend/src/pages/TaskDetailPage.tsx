import type { WorkspaceState } from "../main";
import { CapabilityReadinessPanel } from "../components/CapabilityReadinessPanel";
import { ModelInvocationPanel } from "../components/ModelInvocationPanel";
import { PendingReviewWorkspace } from "../components/PendingReviewWorkspace";
import { ReportExplorer } from "../components/ReportExplorer";
import { StatusBadge } from "../components/StatusBadge";
import { StructureViewerPanel } from "../components/StructureViewerPanel";
import { TaskSearch } from "../components/TaskSearch";

interface TaskDetailPageProps {
  state: WorkspaceState;
  taskId: string;
  onTaskIdChange: (taskId: string) => void;
  onLoadTask: (taskId: string) => void;
  onRefresh: () => void;
}

export function TaskDetailPage({ state, taskId, onTaskIdChange, onLoadTask, onRefresh }: TaskDetailPageProps) {
  const task = state.task;
  return (
    <div className="page-grid two-column">
      <section className="panel intro-panel">
        <div>
          <h2>Task Detail</h2>
          <p>{task ? task.goal : "Load a task to inspect status, context, pending review, and artifacts."}</p>
        </div>
        <TaskSearch taskId={taskId} onTaskIdChange={onTaskIdChange} onSubmit={onLoadTask} onRefresh={onRefresh} />
      </section>
      <section className="panel">
        <div className="panel-header">
          <h2>Task Snapshot</h2>
          <StatusBadge value={task?.status} />
        </div>
        {task ? (
          <dl className="kv">
            <dt>Task ID</dt>
            <dd>{task.id}</dd>
            <dt>Internal status</dt>
            <dd>{task.internal_status}</dd>
            <dt>Created</dt>
            <dd>{task.created_at}</dd>
            <dt>Updated</dt>
            <dd>{task.updated_at}</dd>
            <dt>Pending action</dt>
            <dd>{task.pending_action?.pending_action_id ?? "none"}</dd>
            <dt>Constraints</dt>
            <dd><pre>{JSON.stringify(task.constraints ?? {}, null, 2)}</pre></dd>
          </dl>
        ) : (
          <p className="muted">Task not loaded.</p>
        )}
      </section>
      <PendingReviewWorkspace detail={state.pendingActionDetail} onDecisionSubmitted={onRefresh} />
      <ReportExplorer task={task} report={state.report} />
      <StructureViewerPanel task={task} />
      <ModelInvocationPanel readiness={state.readiness} pendingActionDetail={state.pendingActionDetail} />
      <CapabilityReadinessPanel readiness={state.readiness} />
    </div>
  );
}
