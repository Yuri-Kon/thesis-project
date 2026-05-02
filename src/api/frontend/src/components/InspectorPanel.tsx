import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

export interface InspectorCardDescriptor {
  key: string;
  title: string;
  tone?: "default" | "warning";
  statusBadge?: ReactNode;
  className?: string;
  children: ReactNode;
}

function resolveOrder(stored: readonly string[], cardKeys: readonly string[]): string[] {
  const keySet = new Set(cardKeys);
  const seen = new Set<string>();
  const known = stored.filter((key) => {
    if (!keySet.has(key) || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const newcomers = cardKeys.filter((key) => !seen.has(key));
  return [...known, ...newcomers];
}

function readOrder(pageKey: string): string[] {
  try {
    const raw = localStorage.getItem(`inspector-order:v1:${pageKey}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || !parsed.every((v) => typeof v === "string")) return [];
    return parsed;
  } catch {
    return [];
  }
}

function persistOrder(pageKey: string, order: string[]): void {
  try {
    localStorage.setItem(`inspector-order:v1:${pageKey}`, JSON.stringify(order));
  } catch {
    /* quota exceeded or private mode */
  }
}

interface InspectorPanelProps {
  cards: InspectorCardDescriptor[];
  pageKey: string;
}

export function InspectorPanel({ cards, pageKey }: InspectorPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [order, setOrder] = useState<string[]>(() =>
    resolveOrder(readOrder(pageKey), cards.map((c) => c.key)),
  );
  const liveRef = useRef<HTMLParagraphElement>(null);

  // Re-resolve when cards or pageKey change
  useEffect(() => {
    setOrder(resolveOrder(readOrder(pageKey), cards.map((c) => c.key)));
  }, [cards, pageKey]);

  const cardsByKey = useMemo(() => new Map(cards.map((c) => [c.key, c])), [cards]);

  // Duplicate key warning in dev
  useEffect(() => {
    if (import.meta.env.DEV) {
      const seen = new Set<string>();
      for (const key of cards.map((c) => c.key)) {
        if (seen.has(key)) {
          console.warn(`[InspectorPanel] Duplicate card key: "${key}"`);
        }
        seen.add(key);
      }
    }
  }, [cards]);

  const announce = useCallback((message: string) => {
    const el = liveRef.current;
    if (el) el.textContent = message;
  }, []);

  const moveCard = useCallback(
    (fromIndex: number, toIndex: number) => {
      if (fromIndex === toIndex || toIndex < 0 || toIndex >= order.length) return;
      const next = [...order];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      const safe = resolveOrder(next, cards.map((c) => c.key));
      setOrder(safe);
      persistOrder(pageKey, safe);
      const card = cardsByKey.get(moved);
      if (card) {
        announce(`${card.title} moved to position ${toIndex + 1} of ${order.length}`);
      }
    },
    [order, pageKey, cards, cardsByKey, announce],
  );

  const sorted = useMemo(() => {
    const resolved = resolveOrder(order, cards.map((c) => c.key));
    return resolved.map((key) => cardsByKey.get(key)!);
  }, [order, cards, cardsByKey]);

  if (cards.length === 0) {
    return (
      <aside className={`workbench-inspector${collapsed ? " collapsed" : ""}`} aria-label="Inspector">
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

  const showControls = order.length >= 2;

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
      <div className="inspector-content" role="list" aria-describedby="inspector-reorder-help">
        {sorted.map((card, index) => (
          <section
            key={card.key}
            className={`inspector-card${card.tone === "warning" ? " warning-card" : ""}${card.className ? ` ${card.className}` : ""}`}
            data-card-key={card.key}
            role="listitem"
          >
            <div className="inspector-card__header">
              <h2 className="inspector-card__title">{card.title}</h2>
              {card.statusBadge}
              {showControls ? (
                <>
                  <button
                    type="button"
                    className="inspector-card__move"
                    aria-label={`Move ${card.title} up`}
                    disabled={index === 0}
                    onClick={() => moveCard(index, index - 1)}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="inspector-card__move"
                    aria-label={`Move ${card.title} down`}
                    disabled={index === order.length - 1}
                    onClick={() => moveCard(index, index + 1)}
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    className="drag-handle"
                    aria-label={`Reorder ${card.title}`}
                    aria-describedby="inspector-reorder-help"
                  >
                    ↕
                  </button>
                </>
              ) : null}
            </div>
            <div className="inspector-card__body">{card.children}</div>
          </section>
        ))}
      </div>
      <p id="inspector-reorder-help" className="sr-only">
        Drag cards by the reorder handle, or use the move up and move down buttons.
      </p>
      <p className="sr-only" aria-live="polite" ref={liveRef} />
    </aside>
  );
}
