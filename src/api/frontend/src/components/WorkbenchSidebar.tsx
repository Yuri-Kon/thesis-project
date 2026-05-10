import type { WorkspaceState } from "../main";

interface WorkbenchSidebarProps {
  state: WorkspaceState;
  taskId: string;
  view: string;
  activeIntakeId: string | null;
  onDraftNavigate: (href: string) => void;
}

function navHref(item: string, taskId: string): string {
  if (item === "overview") {
    return "/ui";
  }
  if (item === "task_builder") {
    return "/ui/task-builder";
  }
  if (item === "timeline" && taskId) {
    return `/ui/tasks/${encodeURIComponent(taskId)}/events`;
  }
  if (item === "task_detail" && taskId) {
    return `/ui/tasks/${encodeURIComponent(taskId)}`;
  }
  return "#";
}

function isActive(item: string, view: string): boolean {
  if (item === "overview") {
    return view === "dashboard";
  }
  if (item === "task_builder") {
    return view === "task_builder";
  }
  if (item === "timeline") {
    return view === "event_timeline";
  }
  return view === "task_detail" && item === "task_detail";
}

function navLabel(item: string): string {
  const labels: Record<string, string> = {
    overview: "概览",
    task_builder: "任务构建",
    task_detail: "任务详情",
    timeline: "时间线",
  };
  return labels[item] ?? item;
}

export function WorkbenchSidebar({ state, taskId, view, activeIntakeId, onDraftNavigate }: WorkbenchSidebarProps) {
  const blockedCapabilities = state.readiness.filter((entry) => entry.status === "blocked").length;
  const warningCount = state.readiness.filter((entry) => entry.status === "degraded").length;
  const navItems = ["overview", "task_builder", "task_detail", "timeline"];

  const handleClick = (href: string) => (e: React.MouseEvent) => {
    if (activeIntakeId && view === "task_builder") {
      e.preventDefault();
      onDraftNavigate(href);
    }
  };

  return (
    <aside className="workbench-sidebar" aria-label="工作区侧边栏">
      <div className="sidebar-brand">
        <span className="brand-mark">PD</span>
        <div>
          <strong>蛋白质设计控制台</strong>
          <p>操作工作区</p>
        </div>
      </div>

      <section className="sidebar-attention">
        <div>
          <strong>需要关注</strong>
          <p>待决策、警告和阻塞项。</p>
        </div>
        <span className="counter">{state.pendingActions.length + warningCount + blockedCapabilities}</span>
      </section>

      <nav className="sidebar-nav" aria-label="主导航">
        {navItems.map((item) => {
          const href = navHref(item, taskId);
          const disabled = href === "#";
          return disabled ? (
            <span key={item} className="disabled">
              {navLabel(item)}
            </span>
          ) : (
            <a
              key={item}
              href={href}
              className={isActive(item, view) ? "active" : undefined}
              onClick={handleClick(href)}
            >
              {navLabel(item)}
            </a>
          );
        })}
      </nav>

      <section className="sidebar-filters">
        <p className="eyebrow">筛选</p>
        <details>
          <summary>状态</summary>
          <span>等待 / 运行中 / 已完成 / 失败</span>
        </details>
        <details>
          <summary>类别</summary>
          <span>能力 / 复核 / 产物</span>
        </details>
        <details>
          <summary>时间范围</summary>
          <span>最新工作区数据</span>
        </details>
      </section>
    </aside>
  );
}
