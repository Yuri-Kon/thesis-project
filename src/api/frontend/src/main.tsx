import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { apiClient } from "./api/client";
import type {
  CapabilityReadinessEntry,
  PendingActionDetail,
  PendingActionSummary,
  TaskRecord,
  TaskReportDetail,
  TaskTimelineEvent,
} from "./api/types";
import { DashboardPage } from "./pages/DashboardPage";
import { EventTimelinePage } from "./pages/EventTimelinePage";
import { TaskBuilderPage } from "./pages/TaskBuilderPage";
import { TaskDetailPage } from "./pages/TaskDetailPage";
import { ErrorNotice } from "./components/ErrorNotice";
import "./styles/app.css";

interface BootstrapPayload {
  taskId: string;
  view: "dashboard" | "task_builder" | "task_detail" | "event_timeline";
}

export interface WorkspaceState {
  pendingActions: PendingActionSummary[];
  readiness: CapabilityReadinessEntry[];
  task: TaskRecord | null;
  pendingActionDetail: PendingActionDetail | null;
  events: TaskTimelineEvent[];
  report: TaskReportDetail | null;
  loading: boolean;
  error: string | null;
}

function readBootstrap(): BootstrapPayload {
  const node = document.getElementById("app-bootstrap");
  if (!node?.textContent) {
    return { taskId: "", view: "dashboard" };
  }
  return JSON.parse(node.textContent) as BootstrapPayload;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function App() {
  const bootstrap = useMemo(readBootstrap, []);
  const [taskId, setTaskId] = useState(bootstrap.taskId);
  const [state, setState] = useState<WorkspaceState>({
    pendingActions: [],
    readiness: [],
    task: null,
    pendingActionDetail: null,
    events: [],
    report: null,
    loading: true,
    error: null,
  });

  const loadWorkspace = useCallback(
    async (nextTaskId = taskId) => {
      setState((current) => ({ ...current, loading: true, error: null }));
      try {
        const [pendingActions, readiness] = await Promise.all([
          apiClient.listPendingActions(),
          apiClient.getCapabilityReadiness(),
        ]);
        let task: TaskRecord | null = null;
        let pendingActionDetail: PendingActionDetail | null = null;
        let events: TaskTimelineEvent[] = [];
        let report: TaskReportDetail | null = null;

        if (nextTaskId) {
          task = await apiClient.getTask(nextTaskId);
          events = await apiClient.getTaskEvents(nextTaskId);
          if (task.pending_action?.pending_action_id) {
            pendingActionDetail = await apiClient.getPendingAction(task.pending_action.pending_action_id);
          }
          try {
            report = await apiClient.getTaskReport(nextTaskId);
          } catch {
            report = null;
          }
        }

        setState({
          pendingActions,
          readiness,
          task,
          pendingActionDetail,
          events,
          report,
          loading: false,
          error: null,
        });
      } catch (error) {
        setState((current) => ({
          ...current,
          loading: false,
          error: errorMessage(error),
        }));
      }
    },
    [taskId],
  );

  useEffect(() => {
    if (bootstrap.view === "task_builder") {
      setState((current) => ({ ...current, loading: false, error: null }));
      return;
    }
    void loadWorkspace(bootstrap.taskId);
  }, [bootstrap.taskId, bootstrap.view, loadWorkspace]);

  const openTask = useCallback(
    (nextTaskId: string) => {
      setTaskId(nextTaskId);
      window.history.pushState(null, "", `/ui/tasks/${encodeURIComponent(nextTaskId)}`);
      void loadWorkspace(nextTaskId);
    },
    [loadWorkspace],
  );

  const loadTaskDetail = useCallback(
    (nextTaskId: string) => {
      setTaskId(nextTaskId);
      window.history.pushState(null, "", `/ui/tasks/${encodeURIComponent(nextTaskId)}`);
      void loadWorkspace(nextTaskId);
    },
    [loadWorkspace],
  );

  const loadTaskTimeline = useCallback(
    (nextTaskId: string) => {
      setTaskId(nextTaskId);
      window.history.pushState(null, "", `/ui/tasks/${encodeURIComponent(nextTaskId)}/events`);
      void loadWorkspace(nextTaskId);
    },
    [loadWorkspace],
  );

  const content =
    bootstrap.view === "event_timeline" ? (
      <EventTimelinePage state={state} taskId={taskId} onTaskIdChange={setTaskId} onLoadTask={loadTaskTimeline} onRefresh={() => loadWorkspace(taskId)} />
    ) : bootstrap.view === "task_builder" ? (
      <TaskBuilderPage onOpenTask={openTask} />
    ) : bootstrap.view === "task_detail" ? (
      <TaskDetailPage state={state} taskId={taskId} onTaskIdChange={setTaskId} onLoadTask={loadTaskDetail} onRefresh={() => loadWorkspace(taskId)} />
    ) : (
      <DashboardPage state={state} taskId={taskId} onTaskIdChange={setTaskId} onOpenTask={openTask} onRefresh={() => loadWorkspace(taskId)} />
    );

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Protein Design Workspace</p>
          <h1>Operator Console</h1>
        </div>
        <nav className="topnav" aria-label="Workspace navigation">
          <a href="/ui">Dashboard</a>
          <a href="/ui/task-builder">New Task</a>
          {taskId ? <a href={`/ui/tasks/${encodeURIComponent(taskId)}`}>Task Detail</a> : <span>Task Detail</span>}
          {taskId ? <a href={`/ui/tasks/${encodeURIComponent(taskId)}/events`}>Event Timeline</a> : <span>Event Timeline</span>}
        </nav>
      </header>
      {state.error ? <ErrorNotice message={state.error} /> : null}
      {content}
    </main>
  );
}

const root = document.getElementById("root");
if (!root) {
  throw new Error("React root not found");
}
createRoot(root).render(<App />);
