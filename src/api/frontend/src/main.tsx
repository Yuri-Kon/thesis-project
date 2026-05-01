import React, { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { apiClient, apiErrorMessage } from "./api/client";
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
import { AppErrorBoundary, ColumnErrorBoundary } from "./components/ErrorBoundary";
import { InspectorPanel } from "./components/InspectorPanel";
import { WorkbenchSidebar } from "./components/WorkbenchSidebar";
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

function App() {
  const bootstrap = useMemo(readBootstrap, []);
  const [taskId, setTaskId] = useState(bootstrap.taskId);
  const [activeIntakeId, setActiveIntakeId] = useState<string | null>(null);
  const [draftNavigateHref, setDraftNavigateHref] = useState<string | null>(null);
  const [inspector, setInspector] = useState<ReactNode>(null);
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
          error: apiErrorMessage(error),
        }));
      }
    },
    [taskId],
  );

  const handleActiveIntakeChange = useCallback((intakeId: string | null) => {
    setActiveIntakeId(intakeId);
  }, []);

  const handleDraftNavigate = useCallback((href: string) => {
    setDraftNavigateHref(href);
  }, []);

  const handleResolveDraftNavigate = useCallback(
    (action: "continue" | "discard" | "cancel") => {
      if (action === "discard" && draftNavigateHref) {
        window.location.href = draftNavigateHref;
        return;
      }
      setDraftNavigateHref(null);
    },
    [draftNavigateHref],
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
      <EventTimelinePage state={state} taskId={taskId} onTaskIdChange={setTaskId} onLoadTask={loadTaskTimeline} onRefresh={() => loadWorkspace(taskId)} onInspectorChange={setInspector} />
    ) : bootstrap.view === "task_builder" ? (
      <TaskBuilderPage onOpenTask={openTask} onInspectorChange={setInspector} onActiveIntakeChange={handleActiveIntakeChange} draftNavigateHref={draftNavigateHref} onResolveDraftNavigate={handleResolveDraftNavigate} />
    ) : bootstrap.view === "task_detail" ? (
      <TaskDetailPage state={state} taskId={taskId} onTaskIdChange={setTaskId} onLoadTask={loadTaskDetail} onRefresh={() => loadWorkspace(taskId)} onInspectorChange={setInspector} />
    ) : (
      <DashboardPage state={state} taskId={taskId} onTaskIdChange={setTaskId} onOpenTask={openTask} onRefresh={() => loadWorkspace(taskId)} onInspectorChange={setInspector} activeIntakeId={activeIntakeId} onDraftNavigate={handleDraftNavigate} />
    );

  return (
    <AppErrorBoundary>
      <main className="app-shell">
        <ColumnErrorBoundary name="sidebar">
          <WorkbenchSidebar state={state} taskId={taskId} view={bootstrap.view} activeIntakeId={activeIntakeId} onDraftNavigate={handleDraftNavigate} />
        </ColumnErrorBoundary>
        <ColumnErrorBoundary name="main">
          <section className="workbench-main">
            {state.error ? <ErrorNotice message={state.error} /> : null}
            <div className="workbench-main-scroll">{content}</div>
          </section>
        </ColumnErrorBoundary>
        <ColumnErrorBoundary name="inspector">
          <InspectorPanel>{inspector}</InspectorPanel>
        </ColumnErrorBoundary>
      </main>
    </AppErrorBoundary>
  );
}

const root = document.getElementById("root");
if (!root) {
  throw new Error("React root not found");
}
createRoot(root).render(<App />);
