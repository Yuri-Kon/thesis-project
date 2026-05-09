import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { apiClient, apiErrorMessage } from "../api/client";
import type { TaskRecord, TaskReportDetail } from "../api/types";

interface StructureViewerPanelProps {
  task: TaskRecord | null;
  report: TaskReportDetail | null;
}

type DisplayMode = "cartoon" | "trace" | "backbone" | "sticks" | "all";
type ColorMode = "element" | "chain" | "confidence";

interface AtomPoint {
  serial: number;
  atomName: string;
  residueName: string;
  residueSeq: string;
  chainId: string;
  x: number;
  y: number;
  z: number;
  bFactor: number | null;
  element: string;
}

interface ProjectedAtom {
  atom: AtomPoint;
  x: number;
  y: number;
  z: number;
  radius: number;
}

interface ViewRotation {
  x: number;
  y: number;
}

interface DragState {
  pointerId: number;
  clientX: number;
  clientY: number;
  moved: boolean;
}

interface ViewerOptions {
  atomRadius: number;
  bondWidth: number;
  colorMode: ColorMode;
  displayMode: DisplayMode;
  showLabels: boolean;
  zoom: number;
}

const BACKBONE_ATOMS = new Set(["N", "CA", "C", "O", "P"]);
const CHAIN_COLORS = ["#2f6fbb", "#1f9d68", "#a35bb8", "#c78318", "#d14f45", "#5d6fc5"];

export function StructureViewerPanel({ task, report }: StructureViewerPanelProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const projectionRef = useRef<ProjectedAtom[]>([]);
  const structurePath = report?.structure_pdb_path ?? task?.design_result?.structure_pdb_path ?? null;
  const structureUrl = task ? `/tasks/${encodeURIComponent(task.id)}/structure` : null;
  const [source, setSource] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rotation, setRotation] = useState<ViewRotation>({ x: -0.35, y: 0.55 });
  const [displayMode, setDisplayMode] = useState<DisplayMode>("cartoon");
  const [colorMode, setColorMode] = useState<ColorMode>("confidence");
  const [zoom, setZoom] = useState(1.05);
  const [atomRadius, setAtomRadius] = useState(3.4);
  const [bondWidth, setBondWidth] = useState(16);
  const [showLabels, setShowLabels] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [selectedSerial, setSelectedSerial] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setSource("");
    setError(null);
    setSelectedSerial(null);
    if (!task || !structurePath) {
      setLoading(false);
      return;
    }
    setLoading(true);
    apiClient.getTaskStructure(task.id)
      .then((text) => {
        if (!cancelled) {
          setSource(text);
          setError(null);
        }
      })
      .catch((fetchError: unknown) => {
        if (!cancelled) {
          setError(apiErrorMessage(fetchError));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [structurePath, task]);

  const atoms = useMemo(() => parsePdbAtoms(source), [source]);
  const visibleAtoms = useMemo(() => selectVisibleAtoms(atoms, displayMode), [atoms, displayMode]);
  const selectedAtom = useMemo(
    () => atoms.find((atom) => atom.serial === selectedSerial) ?? null,
    [atoms, selectedSerial],
  );
  const residueSummary = useMemo(() => summarizeResidues(atoms), [atoms]);
  const options = useMemo<ViewerOptions>(
    () => ({ atomRadius, bondWidth, colorMode, displayMode, showLabels, zoom }),
    [atomRadius, bondWidth, colorMode, displayMode, showLabels, zoom],
  );

  useEffect(() => {
    projectionRef.current = renderStructure(
      canvasRef.current,
      visibleAtoms,
      rotation,
      options,
      selectedSerial,
    );
  }, [options, rotation, selectedSerial, visibleAtoms]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return undefined;
    }
    const handleNativeWheel = (event: globalThis.WheelEvent) => {
      event.preventDefault();
      event.stopPropagation();
      const direction = event.deltaY > 0 ? -0.08 : 0.08;
      setZoom((current) => clamp(current + direction, 0.55, 3));
    };
    canvas.addEventListener("wheel", handleNativeWheel, { passive: false });
    return () => {
      canvas.removeEventListener("wheel", handleNativeWheel);
    };
  }, [structurePath]);

  useEffect(() => {
    if (!expanded) {
      return undefined;
    }
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [expanded]);

  function handlePointerDown(event: PointerEvent<HTMLCanvasElement>) {
    dragRef.current = {
      pointerId: event.pointerId,
      clientX: event.clientX,
      clientY: event.clientY,
      moved: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event: PointerEvent<HTMLCanvasElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) {
      return;
    }
    const dx = event.clientX - drag.clientX;
    const dy = event.clientY - drag.clientY;
    dragRef.current = {
      ...drag,
      clientX: event.clientX,
      clientY: event.clientY,
      moved: drag.moved || Math.abs(dx) + Math.abs(dy) > 2,
    };
    setRotation((current) => ({
      x: current.x + dy * 0.01,
      y: current.y + dx * 0.01,
    }));
  }

  function handlePointerEnd(event: PointerEvent<HTMLCanvasElement>) {
    const drag = dragRef.current;
    if (drag?.pointerId !== event.pointerId) {
      return;
    }
    dragRef.current = null;
    if (!drag.moved) {
      selectNearestAtom(event);
    }
  }

  function selectNearestAtom(event: PointerEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    let nearest: ProjectedAtom | null = null;
    let nearestDistance = Number.POSITIVE_INFINITY;
    for (const point of projectionRef.current) {
      const distance = Math.hypot(point.x - x, point.y - y);
      if (distance < nearestDistance) {
        nearest = point;
        nearestDistance = distance;
      }
    }
    setSelectedSerial(nearest && nearestDistance <= Math.max(18, nearest.radius + 10) ? nearest.atom.serial : null);
  }

  function resetView() {
    setRotation({ x: -0.35, y: 0.55 });
    setZoom(1.05);
    setAtomRadius(3.4);
    setBondWidth(16);
    setSelectedSerial(null);
  }

  const panelClassName = `panel structure-viewer-panel${expanded ? " is-expanded" : ""}`;

  return (
    <section className={panelClassName}>
      <div className="panel-header structure-viewer-head">
        <div>
          <h2>Structure Viewer</h2>
          {atoms.length ? (
            <p className="muted">{residueSummary.residueCount} residues · {atoms.length} atoms · {residueSummary.chainCount} chains</p>
          ) : null}
        </div>
        <div className="structure-head-actions">
          {visibleAtoms.length ? <span className="pill">{visibleAtoms.length} shown</span> : null}
          <button type="button" onClick={() => setExpanded((current) => !current)}>
            {expanded ? "Restore" : "Full screen"}
          </button>
        </div>
      </div>
      {structurePath ? (
        <div className="structure-viewer">
          <div className="structure-stage">
            <canvas
              ref={canvasRef}
              className="structure-canvas"
              aria-label="Protein structure molecular viewer"
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerEnd}
              onPointerCancel={handlePointerEnd}
            />
            <div className="structure-stage-badge">
              Drag rotate · Wheel zoom · Click atom
            </div>
          </div>
          <aside className="structure-controls" aria-label="Structure controls">
            <div className="structure-control-grid">
              <label>
                <span>Representation</span>
                <select value={displayMode} onChange={(event) => setDisplayMode(event.target.value as DisplayMode)}>
                  <option value="cartoon">Cartoon ribbon</option>
                  <option value="trace">Trace</option>
                  <option value="backbone">Backbone atoms</option>
                  <option value="sticks">Sticks</option>
                  <option value="all">All atoms</option>
                </select>
              </label>
              <label>
                <span>Color</span>
                <select value={colorMode} onChange={(event) => setColorMode(event.target.value as ColorMode)}>
                  <option value="confidence">Confidence</option>
                  <option value="element">Element</option>
                  <option value="chain">Chain</option>
                </select>
              </label>
              <label>
                <span>Zoom {zoom.toFixed(2)}x</span>
                <input
                  type="range"
                  min="0.55"
                  max="3"
                  step="0.05"
                  value={zoom}
                  onChange={(event) => setZoom(Number(event.target.value))}
                />
              </label>
              <label>
                <span>Atom size {atomRadius.toFixed(1)}</span>
                <input
                  type="range"
                  min="1.5"
                  max="11"
                  step="0.5"
                  value={atomRadius}
                  onChange={(event) => setAtomRadius(Number(event.target.value))}
                />
              </label>
              <label>
                <span>{displayMode === "cartoon" ? "Ribbon width" : "Bond width"} {bondWidth.toFixed(1)}</span>
                <input
                  type="range"
                  min="1"
                  max="28"
                  step="0.5"
                  value={bondWidth}
                  onChange={(event) => setBondWidth(Number(event.target.value))}
                />
              </label>
              <label className="structure-checkbox">
                <input
                  type="checkbox"
                  checked={showLabels}
                  onChange={(event) => setShowLabels(event.target.checked)}
                />
                <span>Show residue labels</span>
              </label>
            </div>
            <div className="structure-toolbar">
              <button type="button" title="Rotate structure left" onClick={() => setRotation((current) => ({ ...current, y: current.y - 0.35 }))}>
                Rotate left
              </button>
              <button type="button" title="Rotate structure right" onClick={() => setRotation((current) => ({ ...current, y: current.y + 0.35 }))}>
                Rotate right
              </button>
              <button type="button" title="Reset structure view" onClick={resetView}>
                Reset
              </button>
              <a className="button-link" href={structureUrl ?? "#"} target="_blank" rel="noreferrer">
                Open PDB
              </a>
            </div>
            <div className="structure-selection">
              <h3>Selected Node</h3>
              {selectedAtom ? (
                <dl className="kv compact-kv structure-meta">
                  <dt>Atom</dt>
                  <dd>{selectedAtom.atomName} #{selectedAtom.serial}</dd>
                  <dt>Residue</dt>
                  <dd>{selectedAtom.residueName} {selectedAtom.residueSeq}</dd>
                  <dt>Chain</dt>
                  <dd>{selectedAtom.chainId || "-"}</dd>
                  <dt>Element</dt>
                  <dd>{selectedAtom.element || "-"}</dd>
                  <dt>Coordinates</dt>
                  <dd>{formatCoord(selectedAtom.x)}, {formatCoord(selectedAtom.y)}, {formatCoord(selectedAtom.z)}</dd>
                  <dt>Confidence</dt>
                  <dd>{selectedAtom.bFactor === null ? "-" : selectedAtom.bFactor.toFixed(2)}</dd>
                </dl>
              ) : (
                <p className="muted">Click a rendered node to inspect atom and residue details.</p>
              )}
            </div>
            <dl className="kv compact-kv structure-meta">
              <dt>Artifact</dt>
              <dd>{structurePath}</dd>
              <dt>Visible atoms</dt>
              <dd>{visibleAtoms.length || "not parsed"}</dd>
              <dt>Total atoms</dt>
              <dd>{atoms.length || "not parsed"}</dd>
            </dl>
            {loading ? <p className="muted">Loading structure artifact...</p> : null}
            {error ? <p className="error-text">{error}</p> : null}
            {!loading && !error && source && atoms.length === 0 ? (
              <p className="muted">Structure file loaded, but no PDB ATOM/HETATM coordinates were parsed.</p>
            ) : null}
          </aside>
        </div>
      ) : (
        <p className="muted">No structure artifact is available for this task.</p>
      )}
    </section>
  );
}

function parsePdbAtoms(source: string): AtomPoint[] {
  const atoms: AtomPoint[] = [];
  for (const line of source.split(/\r?\n/)) {
    if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) {
      continue;
    }
    const point = parsePdbAtomLine(line);
    if (point) {
      atoms.push(point);
    }
  }
  return atoms.slice(0, 6000);
}

function parsePdbAtomLine(line: string): AtomPoint | null {
  const x = Number.parseFloat(line.slice(30, 38));
  const y = Number.parseFloat(line.slice(38, 46));
  const z = Number.parseFloat(line.slice(46, 54));
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
    return null;
  }
  const bFactor = Number.parseFloat(line.slice(60, 66));
  return {
    serial: Number.parseInt(line.slice(6, 11).trim(), 10) || 0,
    atomName: line.slice(12, 16).trim(),
    residueName: line.slice(17, 20).trim(),
    residueSeq: line.slice(22, 26).trim(),
    chainId: line.slice(21, 22).trim(),
    x,
    y,
    z,
    bFactor: Number.isFinite(bFactor) ? bFactor : null,
    element: line.slice(76, 78).trim() || line.slice(12, 13).trim(),
  };
}

function selectVisibleAtoms(atoms: AtomPoint[], mode: DisplayMode): AtomPoint[] {
  if (mode === "all") {
    return atoms;
  }
  if (mode === "sticks") {
    return atoms.filter((atom) => atom.atomName !== "H");
  }
  if (mode === "backbone") {
    return atoms.filter((atom) => BACKBONE_ATOMS.has(atom.atomName));
  }
  const trace = atoms.filter((atom) => atom.atomName === "CA" || atom.atomName === "P");
  return trace.length ? trace : atoms.filter((atom) => BACKBONE_ATOMS.has(atom.atomName));
}

function summarizeResidues(atoms: AtomPoint[]) {
  const residueKeys = new Set<string>();
  const chainKeys = new Set<string>();
  for (const atom of atoms) {
    residueKeys.add(`${atom.chainId}:${atom.residueName}:${atom.residueSeq}`);
    if (atom.chainId) {
      chainKeys.add(atom.chainId);
    }
  }
  return { residueCount: residueKeys.size, chainCount: chainKeys.size || (atoms.length ? 1 : 0) };
}

function renderStructure(
  canvas: HTMLCanvasElement | null,
  atoms: AtomPoint[],
  rotation: ViewRotation,
  options: ViewerOptions,
  selectedSerial: number | null,
): ProjectedAtom[] {
  if (!canvas) {
    return [];
  }
  const rect = canvas.getBoundingClientRect();
  const cssWidth = Math.max(360, rect.width || 720);
  const cssHeight = Math.max(300, rect.height || 480);
  const pixelRatio = window.devicePixelRatio || 1;
  canvas.width = Math.floor(cssWidth * pixelRatio);
  canvas.height = Math.floor(cssHeight * pixelRatio);
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return [];
  }
  ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  ctx.clearRect(0, 0, cssWidth, cssHeight);
  drawViewerBackground(ctx, cssWidth, cssHeight, options.colorMode);

  if (!atoms.length) {
    ctx.fillStyle = "#8e98a8";
    ctx.font = "600 13px Inter, sans-serif";
    ctx.fillText("No parsed coordinates", 18, 28);
    return [];
  }

  const bounds = calculateBounds(atoms);
  const span = Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY, bounds.maxZ - bounds.minZ, 1);
  const scale = Math.min(cssWidth, cssHeight) * 0.72 * options.zoom / span;
  const projected = atoms.map((atom) => {
    const centered = {
      x: atom.x - bounds.centerX,
      y: atom.y - bounds.centerY,
      z: atom.z - bounds.centerZ,
    };
    const rotated = rotatePoint(centered, rotation);
    const depth = normalizedDepth(rotated.z, span);
    return {
      atom,
      x: cssWidth / 2 + rotated.x * scale,
      y: cssHeight / 2 - rotated.y * scale,
      z: rotated.z,
      radius: options.atomRadius * (0.74 + depth * 0.56),
    };
  });

  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  if (options.displayMode === "cartoon") {
    drawCartoonRibbon(ctx, projected, span, options, selectedSerial);
  } else {
    drawBonds(ctx, projected, span, options);
    drawAtoms(ctx, projected, span, options, selectedSerial);
  }
  if (options.showLabels || selectedSerial !== null) {
    drawLabels(ctx, projected, selectedSerial);
  }
  drawAxes(ctx, rotation, cssWidth, cssHeight);
  drawConfidenceLegend(ctx, cssWidth, cssHeight, options.colorMode);
  return projected;
}

function drawCartoonRibbon(
  ctx: CanvasRenderingContext2D,
  projected: ProjectedAtom[],
  span: number,
  options: ViewerOptions,
  selectedSerial: number | null,
) {
  if (projected.length < 2) {
    drawAtoms(ctx, projected, span, options, selectedSerial);
    return;
  }
  ctx.shadowColor = "rgba(35, 45, 62, 0.22)";
  ctx.shadowBlur = 12;
  ctx.shadowOffsetY = 6;
  drawRibbonStroke(ctx, projected, span, options, options.bondWidth + 5, 0.16, true);
  ctx.shadowColor = "transparent";
  ctx.shadowBlur = 0;
  ctx.shadowOffsetY = 0;
  drawRibbonStroke(ctx, projected, span, options, options.bondWidth, 0.94, false);
  drawRibbonStroke(ctx, projected, span, options, Math.max(2, options.bondWidth * 0.22), 0.48, false, true);
  drawRibbonArrowCaps(ctx, projected, span, options);
  drawSidechainHints(ctx, projected, span, options);
  if (selectedSerial !== null) {
    drawAtoms(ctx, projected.filter((point) => point.atom.serial === selectedSerial), span, options, selectedSerial);
  }
}

function drawRibbonStroke(
  ctx: CanvasRenderingContext2D,
  projected: ProjectedAtom[],
  span: number,
  options: ViewerOptions,
  width: number,
  alpha: number,
  outline: boolean,
  highlight = false,
) {
  for (let index = 1; index < projected.length; index += 1) {
    const prev = projected[index - 1];
    const current = projected[index];
    if (prev.atom.chainId !== current.atom.chainId || distance(prev.atom, current.atom) > 5.8) {
      continue;
    }
    const depth = normalizedDepth((prev.z + current.z) / 2, span);
    ctx.strokeStyle = outline
      ? `rgba(31, 41, 55, ${alpha})`
      : ribbonSegmentColor(prev.atom, current.atom, depth, options.colorMode, alpha);
    ctx.lineWidth = width * (0.72 + depth * 0.52);
    ctx.beginPath();
    ctx.moveTo(prev.x, prev.y);
    const midX = (prev.x + current.x) / 2;
    const midY = (prev.y + current.y) / 2;
    const next = projected[index + 1] ?? current;
    const ctrlX = current.x * 0.72 + next.x * 0.28;
    const ctrlY = current.y * 0.72 + next.y * 0.28;
    ctx.quadraticCurveTo(midX, midY, ctrlX, ctrlY);
    ctx.stroke();
    if (highlight) {
      ctx.strokeStyle = `rgba(255, 255, 255, ${0.1 + depth * 0.18})`;
      ctx.lineWidth = Math.max(1, width * 0.5);
      ctx.beginPath();
      ctx.moveTo(prev.x, prev.y - width * 0.18);
      ctx.quadraticCurveTo(midX, midY - width * 0.22, ctrlX, ctrlY - width * 0.18);
      ctx.stroke();
    }
  }
}

function drawRibbonArrowCaps(
  ctx: CanvasRenderingContext2D,
  projected: ProjectedAtom[],
  span: number,
  options: ViewerOptions,
) {
  const stride = Math.max(6, Math.floor(projected.length / 7));
  for (let index = stride; index < projected.length - 1; index += stride) {
    const prev = projected[index - 1];
    const current = projected[index];
    const next = projected[index + 1];
    if (!next || distance(current.atom, next.atom) > 5.8) {
      continue;
    }
    const angle = Math.atan2(next.y - prev.y, next.x - prev.x);
    const depth = normalizedDepth(current.z, span);
    const length = options.bondWidth * (0.85 + depth * 0.25);
    const width = options.bondWidth * (0.46 + depth * 0.16);
    ctx.fillStyle = atomColor(current.atom, depth, options.colorMode, 0.82);
    ctx.beginPath();
    ctx.moveTo(current.x + Math.cos(angle) * length, current.y + Math.sin(angle) * length);
    ctx.lineTo(current.x + Math.cos(angle + 2.35) * width, current.y + Math.sin(angle + 2.35) * width);
    ctx.lineTo(current.x + Math.cos(angle - 2.35) * width, current.y + Math.sin(angle - 2.35) * width);
    ctx.closePath();
    ctx.fill();
  }
}

function drawSidechainHints(
  ctx: CanvasRenderingContext2D,
  projected: ProjectedAtom[],
  span: number,
  options: ViewerOptions,
) {
  const sidechain = projected.filter((point) => !isTraceAtom(point.atom));
  const stride = Math.max(1, Math.ceil(sidechain.length / 34));
  for (let index = 0; index < sidechain.length; index += stride) {
    const point = sidechain[index];
    const depth = normalizedDepth(point.z, span);
    ctx.strokeStyle = `rgba(177, 220, 118, ${0.18 + depth * 0.22})`;
    ctx.lineWidth = Math.max(1, options.bondWidth * 0.08);
    ctx.beginPath();
    ctx.moveTo(point.x, point.y);
    ctx.lineTo(point.x + Math.cos(index) * 12, point.y + Math.sin(index) * 12);
    ctx.stroke();
  }
}

function drawBonds(
  ctx: CanvasRenderingContext2D,
  projected: ProjectedAtom[],
  span: number,
  options: ViewerOptions,
) {
  for (let index = 1; index < projected.length; index += 1) {
    const prev = projected[index - 1];
    const current = projected[index];
    const maxBondLength = isTraceAtom(prev.atom) && isTraceAtom(current.atom) ? 5.2 : 2.25;
    if (prev.atom.chainId !== current.atom.chainId || distance(prev.atom, current.atom) > maxBondLength) {
      continue;
    }
    const depth = normalizedDepth((prev.z + current.z) / 2, span);
    ctx.strokeStyle = `rgba(182, 199, 224, ${0.28 + depth * 0.45})`;
    ctx.lineWidth = options.bondWidth * (0.62 + depth * 0.7);
    ctx.beginPath();
    ctx.moveTo(prev.x, prev.y);
    ctx.lineTo(current.x, current.y);
    ctx.stroke();
  }
}

function drawAtoms(
  ctx: CanvasRenderingContext2D,
  projected: ProjectedAtom[],
  span: number,
  options: ViewerOptions,
  selectedSerial: number | null,
) {
  for (const point of [...projected].sort((left, right) => left.z - right.z)) {
    const depth = normalizedDepth(point.z, span);
    ctx.fillStyle = atomColor(point.atom, depth, options.colorMode);
    ctx.strokeStyle = point.atom.serial === selectedSerial ? "#f8fafc" : "rgba(255, 255, 255, 0.82)";
    ctx.lineWidth = point.atom.serial === selectedSerial ? 2.5 : 1;
    ctx.beginPath();
    ctx.arc(point.x, point.y, point.radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    if (point.atom.serial === selectedSerial) {
      ctx.strokeStyle = "rgba(17, 19, 24, 0.25)";
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.arc(point.x, point.y, point.radius + 5, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
}

function drawLabels(ctx: CanvasRenderingContext2D, projected: ProjectedAtom[], selectedSerial: number | null) {
  const stride = Math.max(1, Math.ceil(projected.length / 70));
  ctx.font = "700 11px Inter, sans-serif";
  ctx.textBaseline = "middle";
  for (let index = 0; index < projected.length; index += 1) {
    const point = projected[index];
    const shouldShow = point.atom.serial === selectedSerial || index % stride === 0;
    if (!shouldShow) {
      continue;
    }
    const label = `${point.atom.residueName}${point.atom.residueSeq}:${point.atom.atomName}`;
    const width = ctx.measureText(label).width + 10;
    const x = point.x + point.radius + 6;
    const y = point.y - 1;
    ctx.fillStyle = "rgba(255, 255, 255, 0.84)";
    ctx.strokeStyle = "rgba(31, 31, 35, 0.12)";
    ctx.lineWidth = 1;
    roundRect(ctx, x, y - 10, width, 20, 6);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#1e2026";
    ctx.fillText(label, x + 5, y);
  }
}

function drawViewerBackground(ctx: CanvasRenderingContext2D, width: number, height: number, colorMode: ColorMode) {
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, "#ffffff");
  gradient.addColorStop(0.6, "#f8fafc");
  gradient.addColorStop(1, "#eef3f8");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(86, 103, 125, 0.08)";
  ctx.lineWidth = 1;
  for (let x = 28; x < width; x += 38) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = 28; y < height; y += 38) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
  ctx.fillStyle = "rgba(31, 41, 55, 0.72)";
  ctx.font = "700 12px Inter, sans-serif";
  ctx.fillText(colorMode === "confidence" ? "Prediction score (pLDDT)" : "Molecular preview", 18, 26);
}

function calculateBounds(atoms: AtomPoint[]) {
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let minZ = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  let maxZ = Number.NEGATIVE_INFINITY;
  for (const atom of atoms) {
    minX = Math.min(minX, atom.x);
    minY = Math.min(minY, atom.y);
    minZ = Math.min(minZ, atom.z);
    maxX = Math.max(maxX, atom.x);
    maxY = Math.max(maxY, atom.y);
    maxZ = Math.max(maxZ, atom.z);
  }
  return {
    minX,
    minY,
    minZ,
    maxX,
    maxY,
    maxZ,
    centerX: (minX + maxX) / 2,
    centerY: (minY + maxY) / 2,
    centerZ: (minZ + maxZ) / 2,
  };
}

function rotatePoint(point: { x: number; y: number; z: number }, rotation: ViewRotation) {
  const cosY = Math.cos(rotation.y);
  const sinY = Math.sin(rotation.y);
  const cosX = Math.cos(rotation.x);
  const sinX = Math.sin(rotation.x);
  const x1 = point.x * cosY + point.z * sinY;
  const z1 = -point.x * sinY + point.z * cosY;
  const y1 = point.y * cosX - z1 * sinX;
  const z2 = point.y * sinX + z1 * cosX;
  return { x: x1, y: y1, z: z2 };
}

function normalizedDepth(z: number, span: number): number {
  return clamp((z / span) + 0.5, 0, 1);
}

function distance(left: AtomPoint, right: AtomPoint): number {
  return Math.hypot(left.x - right.x, left.y - right.y, left.z - right.z);
}

function isTraceAtom(atom: AtomPoint): boolean {
  return atom.atomName === "CA" || atom.atomName === "P";
}

function ribbonSegmentColor(
  prev: AtomPoint,
  current: AtomPoint,
  depth: number,
  colorMode: ColorMode,
  alpha: number,
): string {
  if (colorMode === "confidence") {
    const prevScore = prev.bFactor ?? 70;
    const currentScore = current.bFactor ?? prevScore;
    return confidenceColor((prevScore + currentScore) / 2, alpha);
  }
  return atomColor(current, depth, colorMode, alpha);
}

function atomColor(atom: AtomPoint, depth: number, colorMode: ColorMode, alphaOverride?: number): string {
  const alpha = alphaOverride ?? (0.74 + depth * 0.2);
  if (colorMode === "chain") {
    const chainIndex = Math.abs(hashString(atom.chainId || "A")) % CHAIN_COLORS.length;
    return hexWithAlpha(CHAIN_COLORS[chainIndex], alpha);
  }
  if (colorMode === "confidence") {
    return confidenceColor(atom.bFactor ?? 70, alpha);
  }
  switch (atom.element.toUpperCase()) {
    case "N":
      return `rgba(62, 110, 196, ${alpha})`;
    case "O":
      return `rgba(211, 78, 66, ${alpha})`;
    case "S":
      return `rgba(197, 157, 57, ${alpha})`;
    case "P":
      return `rgba(149, 93, 190, ${alpha})`;
    default:
      return `rgba(55, 137, 93, ${alpha})`;
  }
}

function confidenceColor(score: number, alpha: number): string {
  if (score >= 90) {
    return `rgba(206, 239, 30, ${alpha})`;
  }
  if (score >= 70) {
    return `rgba(108, 210, 76, ${alpha})`;
  }
  if (score >= 50) {
    return `rgba(38, 171, 162, ${alpha})`;
  }
  return `rgba(116, 42, 154, ${alpha})`;
}

function drawConfidenceLegend(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  colorMode: ColorMode,
) {
  if (colorMode !== "confidence" || width < 420 || height < 300) {
    return;
  }
  const legendHeight = Math.min(260, height - 104);
  const x = width - 46;
  const y = 58;
  const gradient = ctx.createLinearGradient(0, y + legendHeight, 0, y);
  gradient.addColorStop(0, "#742a9a");
  gradient.addColorStop(0.5, "#26aba2");
  gradient.addColorStop(0.72, "#6cd24c");
  gradient.addColorStop(1, "#ceef1e");
  ctx.fillStyle = gradient;
  roundRect(ctx, x, y, 18, legendHeight, 4);
  ctx.fill();
  ctx.strokeStyle = "rgba(255, 255, 255, 0.22)";
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.fillStyle = "rgba(31, 41, 55, 0.82)";
  ctx.font = "700 12px Inter, sans-serif";
  for (const item of [
    { label: "100", value: 1 },
    { label: "90", value: 0.9 },
    { label: "70", value: 0.7 },
    { label: "50", value: 0.5 },
    { label: "0", value: 0 },
  ]) {
    ctx.fillText(item.label, x - 32, y + legendHeight - item.value * legendHeight + 4);
  }
}

function drawAxes(ctx: CanvasRenderingContext2D, rotation: ViewRotation, width: number, height: number) {
  if (width < 320 || height < 260) {
    return;
  }
  const origin = { x: 42, y: height - 46 };
  const axes = [
    { label: "X", color: "#e5484d", vector: rotatePoint({ x: 1, y: 0, z: 0 }, rotation) },
    { label: "Y", color: "#42c86b", vector: rotatePoint({ x: 0, y: 1, z: 0 }, rotation) },
    { label: "Z", color: "#4f7cff", vector: rotatePoint({ x: 0, y: 0, z: 1 }, rotation) },
  ];
  ctx.lineWidth = 3;
  ctx.font = "700 10px Inter, sans-serif";
  for (const axis of axes) {
    const end = {
      x: origin.x + axis.vector.x * 30,
      y: origin.y - axis.vector.y * 30,
    };
    ctx.strokeStyle = axis.color;
    ctx.fillStyle = axis.color;
    ctx.beginPath();
    ctx.moveTo(origin.x, origin.y);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(end.x, end.y, 3.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillText(axis.label, end.x + 5, end.y + 4);
  }
}

function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) - hash) + value.charCodeAt(index);
  }
  return hash;
}

function hexWithAlpha(hex: string, alpha: number): string {
  const normalized = hex.replace("#", "");
  const red = Number.parseInt(normalized.slice(0, 2), 16);
  const green = Number.parseInt(normalized.slice(2, 4), 16);
  const blue = Number.parseInt(normalized.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  ctx.lineTo(x + radius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

function formatCoord(value: number): string {
  return value.toFixed(3);
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
