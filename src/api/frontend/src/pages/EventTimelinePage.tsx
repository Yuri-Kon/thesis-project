import { useEffect, useMemo, useState } from "react";
import type { InspectorCardDescriptor } from "../components/InspectorPanel";
import type { WorkspaceState } from "../main";
import { MetricCard } from "../components/MetricCard";
import { StatusBadge } from "../components/StatusBadge";
import { TaskSearch } from "../components/TaskSearch";
import { TimelineSkeleton } from "../components/SkeletonCard";

interface EventTimelinePageProps {
  state: WorkspaceState;
  taskId: string;
  onTaskIdChange: (taskId: string) => void;
  onLoadTask: (taskId: string) => void;
  onRefresh: () => void;
  onInspectorChange: (cards: InspectorCardDescriptor[]) => void;
}

export function EventTimelinePage({ state, taskId, onTaskIdChange, onLoadTask, onRefresh, onInspectorChange }: EventTimelinePageProps) {
  const [showAllEvents, setShowAllEvents] = useState(false);
  const highlighted = state.events.filter((event) => event.highlight).length;
  const latestEvent = state.events[0] ?? null;
  const visibleEvents = useMemo(
    () => (showAllEvents ? state.events : state.events.slice(0, 12)),
    [showAllEvents, state.events],
  );

  useEffect(() => {
    onInspectorChange([
      {
        key: "inspector-overview",
        title: "Inspector",
        statusBadge: <StatusBadge value={state.task?.status} />,
        children: (
          <dl className="kv compact-kv">
            <dt>Task</dt>
            <dd>{state.task?.id ?? (taskId || "none")}</dd>
            <dt>Events</dt>
            <dd>{state.events.length}</dd>
            <dt>Highlighted</dt>
            <dd>{highlighted}</dd>
            <dt>Latest</dt>
            <dd>{latestEvent?.event_type ?? "none"}</dd>
          </dl>
        ),
      },
      {
        key: "timeline-boundary",
        title: "Timeline boundary",
        children: (
          <p>Recent events stay in a bounded scroll area; older entries remain available through the timeline list.</p>
        ),
      },
    ]);
  }, [highlighted, latestEvent?.event_type, onInspectorChange, state.events.length, state.task?.id, state.task?.status, taskId]);

  if (state.loading) {
    return (
      <div className="timeline-layout">
        <TimelineSkeleton />
      </div>
    );
  }

  return (
    <div className="timeline-layout">
      <section className="workspace-hero">
        <div>
          <h2>Event Timeline</h2>
          <p>Events are rendered only from the task event API response.</p>
        </div>
        <TaskSearch taskId={taskId} onTaskIdChange={onTaskIdChange} onSubmit={onLoadTask} onRefresh={onRefresh} />
      </section>
      <section className="metric-strip" aria-label="Timeline overview">
        <MetricCard label="Events" value={state.events.length} detail={`${highlighted} highlighted`} tone={highlighted ? "amber" : "blue"} />
        <MetricCard label="Task status" value={state.task?.status ?? "not loaded"} />
        <MetricCard label="Task" value={state.task?.id ?? (taskId || "none")} detail={state.task?.goal ?? "load a task to inspect event history"} />
      </section>
      <section className="panel timeline-panel">
        <div className="panel-header">
          <div>
            <h2>Timeline</h2>
            <p className="muted">{state.task?.goal ?? "No task loaded."}</p>
          </div>
          <StatusBadge value={state.task?.status} />
        </div>
        <ol className="timeline">
          {state.events.length === 0 ? <li className="muted">No events returned by the API.</li> : null}
          {visibleEvents.map((event) => (
            <li key={`${event.seq}-${event.event_type}`} className={event.highlight ? "highlight" : ""}>
              <div>
                <strong>{event.event_type}</strong>
                <p>{event.summary}</p>
              </div>
              <span>{event.ts ?? "no timestamp"}</span>
            </li>
          ))}
        </ol>
        {state.events.length > visibleEvents.length || showAllEvents ? (
          <button type="button" className="secondary-action" onClick={() => setShowAllEvents((current) => !current)}>
            {showAllEvents ? "Collapse timeline" : `Show ${state.events.length - visibleEvents.length} more`}
          </button>
        ) : null}
      </section>
    </div>
  );
}
