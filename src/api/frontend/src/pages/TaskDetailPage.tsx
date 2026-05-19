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
import { TheoryObjectSummary } from "../components/TheoryObjectSummary";
import { formatLocalTimestamp, statusLabel } from "../utils/displayText";

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
  const pendingLabel = task?.pending_action?.pending_action_id ?? "无";

  useEffect(() => {
    onInspectorChange([
      {
        key: "inspector-overview",
        title: "检查器",
        statusBadge: <StatusBadge value={task?.status} />,
        children: (
          <dl className="kv compact-kv">
            <dt>任务</dt>
            <dd>{task?.id ?? (taskId || "无")}</dd>
            <dt>外部状态</dt>
            <dd>{statusLabel(task?.status)}</dd>
            <dt>内部状态</dt>
            <dd>{statusLabel(task?.internal_status)}</dd>
            <dt>待处理</dt>
            <dd>{pendingLabel}</dd>
            <dt>更新时间</dt>
            <dd>{task?.updated_at ? formatLocalTimestamp(task.updated_at) : "-"}</dd>
          </dl>
        ),
      },
      {
        key: "theory-objects",
        title: "理论对象",
        statusBadge: state.pendingActionDetail ? <span className="pill">核心</span> : undefined,
        children: <TheoryObjectSummary detail={state.pendingActionDetail} />,
      },
      {
        key: "operation",
        title: "操作",
        children: (
          <dl className="kv compact-kv">
            <dt>候选方案</dt>
            <dd>{state.pendingActionDetail?.candidates.length ?? 0}</dd>
            <dt>默认建议</dt>
            <dd>{state.pendingActionDetail?.default_suggestion ?? "无"}</dd>
            <dt>报告</dt>
            <dd>{state.report?.report_path ?? task?.design_result?.report_path ?? "不可用"}</dd>
          </dl>
        ),
      },
    ]);
  }, [onInspectorChange, pendingLabel, state.pendingActionDetail, state.report?.report_path, task, taskId]);

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
          <h2>任务详情</h2>
          <p>{task ? task.goal : "加载任务后查看状态、上下文、待复核内容和产物。"}</p>
        </div>
        <TaskSearch taskId={taskId} onTaskIdChange={onTaskIdChange} onSubmit={onLoadTask} onRefresh={onRefresh} />
      </section>
      <section className="metric-strip" aria-label="任务概览">
        <MetricCard label="外部状态" value={statusLabel(task?.status)} tone={task?.status?.includes("WAITING") ? "amber" : task?.status === "DONE" ? "green" : "blue"} />
        <MetricCard label="内部状态" value={statusLabel(task?.internal_status)} />
        <MetricCard label="待处理操作" value={pendingLabel} detail={task?.updated_at ? `更新于 ${formatLocalTimestamp(task.updated_at)}` : undefined} tone={task?.pending_action ? "amber" : "neutral"} />
      </section>
      <section className="detail-grid">
      <section className="panel">
        <div className="panel-header">
          <h2>任务快照</h2>
          <StatusBadge value={task?.status} />
        </div>
        {task ? (
          <dl className="kv">
            <dt>任务 ID</dt>
            <dd>{task.id}</dd>
            <dt>内部状态</dt>
            <dd>{statusLabel(task.internal_status)}</dd>
            <dt>创建时间</dt>
            <dd>{formatLocalTimestamp(task.created_at)}</dd>
            <dt>更新时间</dt>
            <dd>{formatLocalTimestamp(task.updated_at)}</dd>
            <dt>待处理操作</dt>
            <dd>{task.pending_action?.pending_action_id ?? "无"}</dd>
            <dt>约束</dt>
            <dd><JsonDisclosure title="约束 JSON" value={task.constraints} /></dd>
          </dl>
        ) : (
          <p className="muted">任务未加载。</p>
        )}
      </section>
      <PendingReviewWorkspace detail={state.pendingActionDetail} onDecisionSubmitted={onRefresh} />
      <StructureViewerPanel task={task} report={state.report} />
      <ReportExplorer task={task} report={state.report} />
        <div className="side-stack">
          <ModelInvocationPanel readiness={state.readiness} pendingActionDetail={state.pendingActionDetail} />
          <CapabilityReadinessPanel readiness={state.readiness} />
        </div>
      </section>
    </div>
  );
}
