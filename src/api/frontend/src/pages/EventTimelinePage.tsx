import { useEffect, useMemo, useState } from "react";
import type { InspectorCardDescriptor } from "../components/InspectorPanel";
import type { WorkspaceState } from "../main";
import { MetricCard } from "../components/MetricCard";
import { StatusBadge } from "../components/StatusBadge";
import { TaskSearch } from "../components/TaskSearch";
import { TimelineSkeleton } from "../components/SkeletonCard";
import { formatBeijingTimestamp, statusLabel } from "../utils/displayText";

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
  const latestEvent = state.events[state.events.length - 1] ?? null;
  const visibleEvents = useMemo(
    () => (showAllEvents ? state.events : state.events.slice(0, 12)),
    [showAllEvents, state.events],
  );

  useEffect(() => {
    onInspectorChange([
      {
        key: "inspector-overview",
        title: "检查器",
        statusBadge: <StatusBadge value={state.task?.status} />,
        children: (
          <dl className="kv compact-kv">
            <dt>任务</dt>
            <dd>{state.task?.id ?? (taskId || "无")}</dd>
            <dt>事件</dt>
            <dd>{state.events.length}</dd>
            <dt>高亮</dt>
            <dd>{highlighted}</dd>
            <dt>最新事件</dt>
            <dd>{latestEvent?.event_type ?? "无"}</dd>
          </dl>
        ),
      },
      {
        key: "timeline-boundary",
        title: "时间线边界",
        children: (
          <p>近期事件保留在受限滚动区域，较早记录仍可通过时间线列表查看。</p>
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
          <h2>事件时间线</h2>
          <p>事件仅根据任务事件 API 响应渲染。</p>
        </div>
        <TaskSearch taskId={taskId} onTaskIdChange={onTaskIdChange} onSubmit={onLoadTask} onRefresh={onRefresh} />
      </section>
      <section className="metric-strip" aria-label="时间线概览">
        <MetricCard label="事件" value={state.events.length} detail={`${highlighted} 个高亮`} tone={highlighted ? "amber" : "blue"} />
        <MetricCard label="任务状态" value={statusLabel(state.task?.status)} />
        <MetricCard label="任务" value={state.task?.id ?? (taskId || "无")} detail={state.task?.goal ?? "加载任务后查看事件历史"} />
      </section>
      <section className="panel timeline-panel">
        <div className="panel-header">
          <div>
            <h2>时间线</h2>
            <p className="muted">{state.task?.goal ?? "未加载任务。"}</p>
          </div>
          <StatusBadge value={state.task?.status} />
        </div>
        <ol className="timeline">
          {state.events.length === 0 ? <li className="muted">API 未返回事件。</li> : null}
          {visibleEvents.map((event) => (
            <li key={`${event.seq}-${event.event_type}`} className={event.highlight ? "highlight" : ""}>
              <div>
                <strong>{event.event_type}</strong>
                <p>{event.summary}</p>
              </div>
              <span title={event.ts ?? undefined}>{formatBeijingTimestamp(event.ts)}</span>
            </li>
          ))}
        </ol>
        {state.events.length > visibleEvents.length || showAllEvents ? (
          <button type="button" className="secondary-action" onClick={() => setShowAllEvents((current) => !current)}>
            {showAllEvents ? "收起时间线" : `再显示 ${state.events.length - visibleEvents.length} 条`}
          </button>
        ) : null}
      </section>
    </div>
  );
}
