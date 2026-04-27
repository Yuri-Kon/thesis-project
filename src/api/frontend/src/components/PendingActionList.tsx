import type { PendingActionSummary } from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface PendingActionListProps {
  pendingActions: PendingActionSummary[];
  onOpenTask: (taskId: string) => void;
}

export function PendingActionList({ pendingActions, onOpenTask }: PendingActionListProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Pending Actions</h2>
        <span className="counter">{pendingActions.length}</span>
      </div>
      <div className="dense-list">
        {pendingActions.length === 0 ? <p className="muted">No pending actions.</p> : null}
        {pendingActions.map((item) => (
          <button key={item.pending_action_id} className="list-row interactive" type="button" onClick={() => onOpenTask(item.task_id)}>
            <div>
              <strong>{item.pending_action_id}</strong>
              <p>{item.summary}</p>
            </div>
            <StatusBadge value={item.status} />
            <span>{item.task_id}</span>
            <span>{item.candidate_count} candidates</span>
          </button>
        ))}
      </div>
    </section>
  );
}
