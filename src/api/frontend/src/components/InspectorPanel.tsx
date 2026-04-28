import { useState } from "react";
import type { ReactNode } from "react";

interface InspectorPanelProps {
  children: ReactNode;
}

export function InspectorPanel({ children }: InspectorPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside className={collapsed ? "workbench-inspector collapsed" : "workbench-inspector"} aria-label="Inspector">
      <button
        type="button"
        className="inspector-toggle"
        aria-expanded={!collapsed}
        title={collapsed ? "Show inspector" : "Hide inspector"}
        onClick={() => setCollapsed((current) => !current)}
      >
        {collapsed ? "Inspect" : "Hide"}
      </button>
      <div className="inspector-content">{children}</div>
    </aside>
  );
}
