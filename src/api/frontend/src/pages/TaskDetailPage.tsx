import { useEffect } from "react";
import type { InspectorCardDescriptor } from "../components/InspectorPanel";
import type { WorkspaceState } from "../main";
import { CapabilityReadinessPanel } from "../components/CapabilityReadinessPanel";
import { JsonDisclosure } from "../components/JsonDisclosure";
import { MetricCard } from "../components/MetricCard";
import { ModelInvocationPanel } from "../components/ModelInvocationPanel";
import { PendingReviewWorkspace } from "../components/PendingReviewWorkspace";
import { ReportExplorer } from "../components/ReportExplorer";
import { StatusBadge } from "../components/StatusBadge";
import { StructureViewerPanel } from "../components/StructureViewerPanel";
import { TaskDetailSkeleton } from "../components/SkeletonCard";
import { TaskSearch } from "../components/TaskSearch";

interface TaskDetailPageProps {
  state: WorkspaceState;
  taskId: string;
  onTaskIdChange: (taskId: string) => void;
  onLoadTask: (taskId: string) => void;
  onRefresh: () => void;
  onInspectorChange: (cards: InspectorCardDescriptor[]) => void;
}

export function TaskDetailPage({ state, taskId, onTaskIdChange, onLoadTask, onRefresh, onInspectorChange }: TaskDetailPageProps) {
  const task = state.task;
  const pendingLabel = task?.pending_action?.pending_action_id ?? "none";

  useEffect(() => {
    onInspectorChange([
      {
        key: "inspector-overview",
        title: "Inspector",
        statusBadge: <StatusBadge value={task?.status} />,
        children: (
          <dl className="kv compact-kv">
            <dt>Task</dt>
            <dd>{task?.id ?? (taskId || "none")}</dd>
            <dt>External</dt>
            <dd>{task?.status ?? "not loaded"}</dd>
            <dt>Internal</dt>
            <dd>{task?.internal_status ?? "not loaded"}</dd>
            <dt>Pending</dt>
            <dd>{pendingLabel}</dd>
            <dt>Updated</dt>
            <dd>{task?.updated_at ?? "-"}</dd>
          </dl>
        ),
      },
      {
        key: "operation",
        title: "Operation",
        children: (
          <dl className="kv compact-kv">
            <dt>Candidates</dt>
            <dd>{state.pendingActionDetail?.candidates.length ?? 0}</dd>
            <dt>Default</dt>
            <dd>{state.pendingActionDetail?.default_suggestion ?? "none"}</dd>
            <dt>Report</dt>
            <dd>{state.report?.report_path ?? task?.design_result?.report_path ?? "not available"}</dd>
          </dl>
        ),
      },
    ]);
  }, [onInspectorChange, pendingLabel, state.pendingActionDetail?.candidates.length, state.pendingActionDetail?.default_suggestion, state.report?.report_path, task, taskId]);

  if (state.loading) {
    return (
      <div className="task-detail-layout">
        <TaskDetailSkeleton />
      </div>
    );
  }

  return (
    <div className="task-detail-layout">
      <section className="workspace-hero">
        <div>
          <h2>Task Detail</h2>
          <p>{task ? task.goal : "Load a task to inspect status, context, pending review, and artifacts."}</p>
        </div>
        <TaskSearch taskId={taskId} onTaskIdChange={onTaskIdChange} onSubmit={onLoadTask} onRefresh={onRefresh} />
      </section>
      <section className="metric-strip" aria-label="Task overview">
        <MetricCard label="External status" value={task?.status ?? "not loaded"} tone={task?.status?.includes("WAITING") ? "amber" : task?.status === "DONE" ? "green" : "blue"} />
        <MetricCard label="Internal state" value={task?.internal_status ?? "not loaded"} />
        <MetricCard label="Pending action" value={pendingLabel} detail={task?.updated_at ? `updated ${task.updated_at}` : undefined} tone={task?.pending_action ? "amber" : "neutral"} />
      </section>
      <section className="detail-grid">
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
            <dd><JsonDisclosure title="Constraints JSON" value={task.constraints} /></dd>
          </dl>
        ) : (
          <p className="muted">Task not loaded.</p>
        )}
      </section>
      <PendingReviewWorkspace detail={state.pendingActionDetail} onDecisionSubmitted={onRefresh} />
      <ReportExplorer task={task} report={state.report} />
      <StructureViewerPanel task={task} />
        <div className="side-stack">
          <ModelInvocationPanel readiness={state.readiness} pendingActionDetail={state.pendingActionDetail} />
          <CapabilityReadinessPanel readiness={state.readiness} />
        </div>
      </section>
    </div>
  );
}
