import type { WorkspaceState } from "../main";

interface WorkbenchSidebarProps {
  state: WorkspaceState;
  taskId: string;
  view: string;
}

function navHref(item: string, taskId: string): string {
  if (item === "Overview") {
    return "/ui";
  }
  if (item === "Task Builder") {
    return "/ui/task-builder";
  }
  if (item === "Timeline" && taskId) {
    return `/ui/tasks/${encodeURIComponent(taskId)}/events`;
  }
  if ((item === "Task Detail" || item === "Review" || item === "Explorer") && taskId) {
    return `/ui/tasks/${encodeURIComponent(taskId)}`;
  }
  return "#";
}

function isActive(item: string, view: string): boolean {
  if (item === "Overview") {
    return view === "dashboard";
  }
  if (item === "Task Builder") {
    return view === "task_builder";
  }
  if (item === "Timeline") {
    return view === "event_timeline";
  }
  return view === "task_detail" && ["Task Detail", "Review", "Explorer"].includes(item);
}

export function WorkbenchSidebar({ state, taskId, view }: WorkbenchSidebarProps) {
  const blockedCapabilities = state.readiness.filter((entry) => entry.status === "blocked").length;
  const warningCount = state.readiness.filter((entry) => entry.status === "degraded").length;
  const navItems = ["Overview", "Task Builder", "Task Detail", "Review", "Timeline", "Explorer"];

  return (
    <aside className="workbench-sidebar" aria-label="Workspace sidebar">
      <div className="sidebar-brand">
        <span className="brand-mark">PD</span>
        <div>
          <strong>Protein Design Console</strong>
          <p>Operator workspace</p>
        </div>
      </div>

      <section className="sidebar-attention">
        <div>
          <strong>Needs attention</strong>
          <p>Pending decisions, warnings, and blockers.</p>
        </div>
        <span className="counter">{state.pendingActions.length + warningCount + blockedCapabilities}</span>
      </section>

      <nav className="sidebar-nav" aria-label="Primary navigation">
        {navItems.map((item) => {
          const href = navHref(item, taskId);
          const disabled = href === "#";
          return disabled ? (
            <span key={item} className="disabled">
              {item}
            </span>
          ) : (
            <a key={item} href={href} className={isActive(item, view) ? "active" : undefined}>
              {item}
            </a>
          );
        })}
      </nav>

      <section className="sidebar-filters">
        <p className="eyebrow">Filters</p>
        <details>
          <summary>Status</summary>
          <span>waiting / running / done / failed</span>
        </details>
        <details>
          <summary>Category</summary>
          <span>capability / review / artifact</span>
        </details>
        <details>
          <summary>Time range</summary>
          <span>latest workspace data</span>
        </details>
      </section>
    </aside>
  );
}
