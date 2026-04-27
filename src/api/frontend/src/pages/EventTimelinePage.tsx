import type { WorkspaceState } from "../main";
import { StatusBadge } from "../components/StatusBadge";
import { TaskSearch } from "../components/TaskSearch";

interface EventTimelinePageProps {
  state: WorkspaceState;
  taskId: string;
  onTaskIdChange: (taskId: string) => void;
  onLoadTask: (taskId: string) => void;
  onRefresh: () => void;
}

export function EventTimelinePage({ state, taskId, onTaskIdChange, onLoadTask, onRefresh }: EventTimelinePageProps) {
  return (
    <div className="page-grid">
      <section className="panel intro-panel">
        <div>
          <h2>Event Timeline</h2>
          <p>Events are rendered only from the task event API response.</p>
        </div>
        <TaskSearch taskId={taskId} onTaskIdChange={onTaskIdChange} onSubmit={onLoadTask} onRefresh={onRefresh} />
      </section>
      <section className="panel">
        <div className="panel-header">
          <h2>Task Snapshot</h2>
          <StatusBadge value={state.task?.status} />
        </div>
        <p className="muted">{state.task?.goal ?? "Load a task to inspect event history."}</p>
      </section>
      <section className="panel timeline-panel">
        <div className="panel-header">
          <h2>Timeline</h2>
          <span className="counter">{state.events.length}</span>
        </div>
        <ol className="timeline">
          {state.events.length === 0 ? <li className="muted">No events returned by the API.</li> : null}
          {state.events.map((event) => (
            <li key={`${event.seq}-${event.event_type}`} className={event.highlight ? "highlight" : ""}>
              <div>
                <strong>{event.event_type}</strong>
                <p>{event.summary}</p>
              </div>
              <span>{event.ts ?? "no timestamp"}</span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
