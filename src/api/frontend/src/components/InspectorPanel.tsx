import { useState } from "react";
import type { ReactNode } from "react";

export interface InspectorCardDescriptor {
  key: string;
  title: string;
  tone?: "default" | "warning";
  statusBadge?: ReactNode;
  className?: string;
  children: ReactNode;
}

interface InspectorPanelProps {
  cards: InspectorCardDescriptor[];
  pageKey: string;
}

export function InspectorPanel({ cards }: InspectorPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  if (cards.length === 0) {
    return (
      <aside className="workbench-inspector" aria-label="Inspector">
        <button
          type="button"
          className="inspector-toggle"
          aria-expanded={!collapsed}
          title={collapsed ? "Show inspector" : "Hide inspector"}
          onClick={() => setCollapsed((c) => !c)}
        >
          {collapsed ? "Inspect" : "Collapse"}
        </button>
      </aside>
    );
  }

  return (
    <aside className={collapsed ? "workbench-inspector collapsed" : "workbench-inspector"} aria-label="Inspector">
      <button
        type="button"
        className="inspector-toggle"
        aria-expanded={!collapsed}
        title={collapsed ? "Show inspector" : "Hide inspector"}
        onClick={() => setCollapsed((c) => !c)}
      >
        {collapsed ? "Inspect" : "Collapse"}
      </button>
      <div className="inspector-content">
        {cards.map((card) => (
          <section
            key={card.key}
            className={`inspector-card${card.tone === "warning" ? " warning-card" : ""}${card.className ? ` ${card.className}` : ""}`}
          >
            <div className="inspector-card__body">{card.children}</div>
          </section>
        ))}
      </div>
    </aside>
  );
}
