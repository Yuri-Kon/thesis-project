import { type ReactNode, useEffect } from "react";
import type { WorkspaceState } from "../main";
import { CapabilityReadinessPanel } from "../components/CapabilityReadinessPanel";
import { MetricCard } from "../components/MetricCard";
import { ModelInvocationPanel } from "../components/ModelInvocationPanel";
import { PendingActionList } from "../components/PendingActionList";
import { TaskSearch } from "../components/TaskSearch";

interface DashboardPageProps {
  state: WorkspaceState;
  taskId: string;
  onTaskIdChange: (taskId: string) => void;
  onOpenTask: (taskId: string) => void;
  onRefresh: () => void;
  onInspectorChange: (content: ReactNode) => void;
}

export function DashboardPage({ state, taskId, onTaskIdChange, onOpenTask, onRefresh, onInspectorChange }: DashboardPageProps) {
  const blockedCapabilities = state.readiness.filter((entry) => entry.status === "blocked").length;
  const degradedCapabilities = state.readiness.filter((entry) => entry.status === "degraded").length;

  useEffect(() => {
    onInspectorChange(
      <>
        <section className="inspector-card">
          <div className="panel-header">
            <h2>Inspector</h2>
            <span className="pill">overview</span>
          </div>
          <dl className="kv compact-kv">
            <dt>Pending</dt>
            <dd>{state.pendingActions.length}</dd>
            <dt>Capabilities</dt>
            <dd>{state.readiness.length}</dd>
            <dt>Blocked</dt>
            <dd>{blockedCapabilities}</dd>
            <dt>Loaded task</dt>
            <dd>{state.task?.id ?? "none"}</dd>
          </dl>
        </section>
        <section className="inspector-card warning-card">
          <h2>Action required</h2>
          <p>{state.pendingActions.length ? "Open a pending action to review candidates and submit a decision." : "No pending review is currently reported by the API."}</p>
          <a className="inspector-action" href="/ui/task-builder">New intake</a>
        </section>
      </>,
    );
  }, [blockedCapabilities, onInspectorChange, state.pendingActions.length, state.readiness.length, state.task?.id]);

  return (
    <div className="dashboard-layout">
      <section className="workspace-hero">
        <div>
          <p className="eyebrow">Operator Console</p>
          <h2>Dashboard</h2>
          <p>Review queue, task lookup, and capability health from the public API boundary.</p>
        </div>
        <TaskSearch taskId={taskId} onTaskIdChange={onTaskIdChange} onSubmit={onOpenTask} onRefresh={onRefresh} />
      </section>
      {state.loading ? <p className="muted">Loading workspace data...</p> : null}
      <section className="metric-strip" aria-label="Workspace overview">
        <MetricCard label="Pending reviews" value={state.pendingActions.length} detail="human decisions waiting" tone={state.pendingActions.length ? "amber" : "green"} />
        <MetricCard label="Capabilities" value={state.readiness.length} detail={`${blockedCapabilities} blocked - ${degradedCapabilities} degraded`} tone={blockedCapabilities ? "red" : degradedCapabilities ? "amber" : "blue"} />
        <MetricCard label="Loaded task" value={state.task?.status ?? "none"} detail={state.task?.id ?? "open a task to inspect"} />
      </section>
      <section className="dashboard-grid">
        <PendingActionList pendingActions={state.pendingActions} onOpenTask={onOpenTask} />
        <div className="side-stack">
          <CapabilityReadinessPanel readiness={state.readiness} />
          <ModelInvocationPanel readiness={state.readiness} pendingActionDetail={state.pendingActionDetail} />
        </div>
      </section>
    </div>
  );
}
