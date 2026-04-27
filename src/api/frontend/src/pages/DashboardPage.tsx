import type { WorkspaceState } from "../main";
import { CapabilityReadinessPanel } from "../components/CapabilityReadinessPanel";
import { ModelInvocationPanel } from "../components/ModelInvocationPanel";
import { PendingActionList } from "../components/PendingActionList";
import { TaskSearch } from "../components/TaskSearch";

interface DashboardPageProps {
  state: WorkspaceState;
  taskId: string;
  onTaskIdChange: (taskId: string) => void;
  onOpenTask: (taskId: string) => void;
  onRefresh: () => void;
}

export function DashboardPage({ state, taskId, onTaskIdChange, onOpenTask, onRefresh }: DashboardPageProps) {
  return (
    <div className="page-grid">
      <section className="panel intro-panel">
        <div>
          <h2>Dashboard</h2>
          <p>Pending review queue, capability health, and task lookup share the same API boundary.</p>
        </div>
        <TaskSearch taskId={taskId} onTaskIdChange={onTaskIdChange} onSubmit={onOpenTask} onRefresh={onRefresh} />
      </section>
      {state.loading ? <p className="muted">Loading workspace data...</p> : null}
      <PendingActionList pendingActions={state.pendingActions} onOpenTask={onOpenTask} />
      <CapabilityReadinessPanel readiness={state.readiness} />
      <ModelInvocationPanel readiness={state.readiness} pendingActionDetail={state.pendingActionDetail} />
    </div>
  );
}
