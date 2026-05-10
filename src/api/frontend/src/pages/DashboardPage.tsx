import { useEffect } from "react";
import type { InspectorCardDescriptor } from "../components/InspectorPanel";
import type { WorkspaceState } from "../main";
import { CapabilityReadinessPanel } from "../components/CapabilityReadinessPanel";
import { MetricCard } from "../components/MetricCard";
import { ModelInvocationPanel } from "../components/ModelInvocationPanel";
import { PendingActionList } from "../components/PendingActionList";
import { TaskSearch } from "../components/TaskSearch";
import { DashboardSkeleton } from "../components/SkeletonCard";
import { statusLabel } from "../utils/displayText";

interface DashboardPageProps {
  state: WorkspaceState;
  taskId: string;
  onTaskIdChange: (taskId: string) => void;
  onOpenTask: (taskId: string) => void;
  onRefresh: () => void;
  onInspectorChange: (cards: InspectorCardDescriptor[]) => void;
  activeIntakeId: string | null;
  onDraftNavigate: (href: string) => void;
}

export function DashboardPage({ state, taskId, onTaskIdChange, onOpenTask, onRefresh, onInspectorChange, activeIntakeId, onDraftNavigate }: DashboardPageProps) {
  const blockedCapabilities = state.readiness.filter((entry) => entry.status === "blocked").length;
  const degradedCapabilities = state.readiness.filter((entry) => entry.status === "degraded").length;

  const handleNewIntakeClick = (e: React.MouseEvent) => {
    if (activeIntakeId) {
      e.preventDefault();
      onDraftNavigate("/ui/task-builder");
    }
  };

  useEffect(() => {
    onInspectorChange([
      {
        key: "inspector-overview",
        title: "检查器",
        statusBadge: <span className="pill">概览</span>,
        children: (
          <dl className="kv compact-kv">
            <dt>待处理</dt>
            <dd>{state.pendingActions.length}</dd>
            <dt>能力</dt>
            <dd>{state.readiness.length}</dd>
            <dt>阻塞</dt>
            <dd>{blockedCapabilities}</dd>
            <dt>已加载任务</dt>
            <dd>{state.task?.id ?? "无"}</dd>
          </dl>
        ),
      },
      {
        key: "action-required",
        title: "需要处理",
        tone: "warning",
        children: (
          <>
            <p>{state.pendingActions.length ? "打开待处理操作，复核候选方案并提交决策。" : "API 当前没有返回待复核操作。"}</p>
            <a className="inspector-action" href="/ui/task-builder" onClick={handleNewIntakeClick}>新建任务录入</a>
          </>
        ),
      },
    ]);
  }, [blockedCapabilities, onInspectorChange, state.pendingActions.length, state.readiness.length, state.task?.id, activeIntakeId, onDraftNavigate]);

  if (state.loading) {
    return (
      <div className="dashboard-layout">
        <DashboardSkeleton />
      </div>
    );
  }

  return (
    <div className="dashboard-layout">
      <section className="workspace-hero">
        <div>
          <p className="eyebrow">操作控制台</p>
          <h2>仪表盘</h2>
          <p>从公共 API 边界查看复核队列、任务查询和能力健康状态。</p>
        </div>
        <TaskSearch taskId={taskId} onTaskIdChange={onTaskIdChange} onSubmit={onOpenTask} onRefresh={onRefresh} />
      </section>
      <section className="metric-strip" aria-label="工作区概览">
        <MetricCard label="待复核" value={state.pendingActions.length} detail="等待人工决策" tone={state.pendingActions.length ? "amber" : "green"} />
        <MetricCard label="能力" value={state.readiness.length} detail={`${blockedCapabilities} 个阻塞 · ${degradedCapabilities} 个降级`} tone={blockedCapabilities ? "red" : degradedCapabilities ? "amber" : "blue"} />
        <MetricCard label="已加载任务" value={statusLabel(state.task?.status)} detail={state.task?.id ?? "打开任务后可查看"} />
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
