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

  // --- Drag state (ref for performance, state for rendering) ---
  interface DragSession {
    activeKey: string;
    pointerId: number;
    originY: number;
    cardRects: Map<string, DOMRect>;
    dropIndex: number | null;
    frameId: number | null;
  }

  const dragRef = useRef<DragSession | null>(null);
  const [dragState, setDragState] = useState<{ activeKey: string; dropIndex: number | null } | null>(null);
  const cardRefs = useRef<Map<string, HTMLElement>>(new Map());

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
        announce(`${card.title} 已移动到第 ${toIndex + 1} 位，共 ${order.length} 位`);
      }
    },
    [order, pageKey, cards, cardsByKey, announce],
  );

  // --- Pointer event handlers ---

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLButtonElement>) => {
      if (!e.isPrimary) return;
      const handleEl = e.currentTarget;
      const cardEl = handleEl.closest(".inspector-card") as HTMLElement | null;
      if (!cardEl) return;
      const key = cardEl.dataset.cardKey;
      if (!key) return;
      if (order.length < 2) return;

      handleEl.setPointerCapture(e.pointerId);

      const cardRects = new Map<string, DOMRect>();
      cardRefs.current.forEach((el, k) => {
        cardRects.set(k, el.getBoundingClientRect());
      });

      dragRef.current = {
        activeKey: key,
        pointerId: e.pointerId,
        originY: e.clientY,
        cardRects,
        dropIndex: null,
        frameId: null,
      };
    },
    [order.length],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLButtonElement>) => {
      const session = dragRef.current;
      if (!session || e.pointerId !== session.pointerId) return;

      const dy = e.clientY - session.originY;
      if (Math.abs(dy) < 4 && session.dropIndex === null) return;

      if (session.frameId !== null) {
        cancelAnimationFrame(session.frameId);
      }

      session.frameId = requestAnimationFrame(() => {
        session.frameId = null;

        let dropIndex = -1;
        const activeIdx = order.indexOf(session.activeKey);

        for (let i = 0; i < order.length; i++) {
          if (i === activeIdx) continue;
          const rect = session.cardRects.get(order[i]);
          if (!rect) continue;
          const midY = rect.top + rect.height / 2;
          if (e.clientY < midY) {
            dropIndex = i;
            break;
          }
          dropIndex = i + 1;
        }

        if (dropIndex > activeIdx) {
          dropIndex = Math.max(0, dropIndex - 1);
        }
        if (dropIndex === activeIdx) {
          dropIndex = -1;
        }

        session.dropIndex = dropIndex;
        setDragState({ activeKey: session.activeKey, dropIndex: dropIndex >= 0 ? dropIndex : null });
      });
    },
    [order],
  );

  const finishDrag = useCallback(
    (card: InspectorCardDescriptor, dropIndex: number | null) => {
      const fromIdx = order.indexOf(card.key);
      if (
        dropIndex !== null &&
        dropIndex >= 0 &&
        dropIndex < order.length &&
        fromIdx !== dropIndex
      ) {
        const next = [...order];
        const [moved] = next.splice(fromIdx, 1);
        next.splice(dropIndex, 0, moved);
        const safe = resolveOrder(next, cards.map((c) => c.key));
        setOrder(safe);
        persistOrder(pageKey, safe);
        announce(`${card.title} 已移动到第 ${dropIndex + 1} 位，共 ${order.length} 位`);
      }
    },
    [order, pageKey, cards, announce],
  );

  const cleanupDrag = useCallback(() => {
    const session = dragRef.current;
    if (!session) return;
    if (session.frameId !== null) {
      cancelAnimationFrame(session.frameId);
    }
    dragRef.current = null;
    setDragState(null);
  }, []);

  const handlePointerUp = useCallback(
    (e: React.PointerEvent<HTMLButtonElement>) => {
      const session = dragRef.current;
      if (!session || e.pointerId !== session.pointerId) return;
      e.currentTarget.releasePointerCapture(e.pointerId);
      const card = cardsByKey.get(session.activeKey);
      const dropIndex = session.dropIndex;
      cleanupDrag();
      if (card && dropIndex !== null) {
        finishDrag(card, dropIndex);
      }
    },
    [cardsByKey, cleanupDrag, finishDrag],
  );

  const handlePointerCancel = useCallback(
    (e: React.PointerEvent<HTMLButtonElement>) => {
      const session = dragRef.current;
      if (!session || e.pointerId !== session.pointerId) return;
      cleanupDrag();
      announce("已取消排序");
    },
    [cleanupDrag, announce],
  );

  // Global Escape during drag
  useEffect(() => {
    if (!dragState) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && dragRef.current) {
        cleanupDrag();
        announce("已取消排序");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [dragState, cleanupDrag, announce]);

  // Cancel drag on collapse
  useEffect(() => {
    if (collapsed && dragRef.current) {
      cleanupDrag();
    }
  }, [collapsed, cleanupDrag]);

  const sorted = useMemo(() => {
    const resolved = resolveOrder(order, cards.map((c) => c.key));
    return resolved.map((key) => cardsByKey.get(key)!);
  }, [order, cards, cardsByKey]);

  if (cards.length === 0) {
    return (
      <aside className={`workbench-inspector${collapsed ? " collapsed" : ""}`} aria-label="检查器">
        <button
          type="button"
          className="inspector-toggle"
          aria-expanded={!collapsed}
          title={collapsed ? "显示检查器" : "隐藏检查器"}
          onClick={() => setCollapsed((c) => !c)}
        >
          {collapsed ? "检查" : "收起"}
        </button>
      </aside>
    );
  }

  const showControls = order.length >= 2;

  return (
    <aside
        className={
          collapsed
            ? "workbench-inspector collapsed"
            : `workbench-inspector${dragState ? " is-reordering" : ""}`
        }
        aria-label="检查器"
      >
      <button
        type="button"
        className="inspector-toggle"
        aria-expanded={!collapsed}
        title={collapsed ? "显示检查器" : "隐藏检查器"}
        onClick={() => setCollapsed((c) => !c)}
      >
        {collapsed ? "检查" : "收起"}
      </button>
      <div
        className={`inspector-content${dragState ? " has-drag" : ""}`}
        role="list"
        aria-describedby="inspector-reorder-help"
      >
        {sorted.map((card, index) => {
          const toneClass = card.tone === "warning" ? " warning-card" : "";
          const dragClass =
            dragState?.activeKey === card.key ? " is-dragging" : "";
          const extraClass = card.className ? ` ${card.className}` : "";

          return (
            <Fragment key={card.key}>
              {dragState &&
              dragState.dropIndex !== null &&
              dragState.dropIndex === index &&
              dragState.activeKey !== card.key ? (
                <div className="inspector-drop-indicator" />
              ) : null}
              <section
                ref={(el) => {
                  if (el) cardRefs.current.set(card.key, el);
                  else cardRefs.current.delete(card.key);
                }}
                className={`inspector-card${toneClass}${dragClass}${extraClass}`}
                data-card-key={card.key}
                role="listitem"
              >
                <div className="inspector-card__header">
                  <h2 className="inspector-card__title">{card.title}</h2>
                  <div className="inspector-card__header-actions">
                    {card.statusBadge}
                    {showControls ? (
                      <>
                        <button
                          type="button"
                          className="inspector-card__move"
                          aria-label={`上移 ${card.title}`}
                          disabled={index === 0}
                          onClick={() => moveCard(index, index - 1)}
                        >
                          ↑
                        </button>
                        <button
                          type="button"
                          className="inspector-card__move"
                          aria-label={`下移 ${card.title}`}
                          disabled={index === order.length - 1}
                          onClick={() => moveCard(index, index + 1)}
                        >
                          ↓
                        </button>
                        <button
                          type="button"
                          className="drag-handle"
                          aria-label={`调整 ${card.title} 顺序`}
                          aria-describedby="inspector-reorder-help"
                          onPointerDown={handlePointerDown}
                          onPointerMove={handlePointerMove}
                          onPointerUp={handlePointerUp}
                          onPointerCancel={handlePointerCancel}
                        >
                          ↕
                        </button>
                      </>
                    ) : null}
                  </div>
                </div>
                <div className="inspector-card__body">{card.children}</div>
              </section>
            </Fragment>
          );
        })}
      </div>
      <p id="inspector-reorder-help" className="sr-only">
        通过排序手柄拖动卡片，或使用上移和下移按钮。
      </p>
      <p className="sr-only" aria-live="polite" ref={liveRef} />
    </aside>
  );
}
