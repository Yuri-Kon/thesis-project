import type { ReactNode } from "react";

interface InspectorPanelProps {
  children: ReactNode;
}

export function InspectorPanel({ children }: InspectorPanelProps) {
  return (
    <aside className="workbench-inspector" aria-label="Inspector">
      {children}
    </aside>
  );
}
