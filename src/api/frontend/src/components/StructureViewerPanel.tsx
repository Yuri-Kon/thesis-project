import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { apiClient, apiErrorMessage } from "../api/client";
import type { TaskRecord, TaskReportDetail } from "../api/types";

interface StructureViewerPanelProps {
  task: TaskRecord | null;
  report: TaskReportDetail | null;
}

interface AtomPoint {
  serial: number;
  atomName: string;
  residueName: string;
  residueSeq: string;
  chainId: string;
  x: number;
  y: number;
  z: number;
  element: string;
}

interface ViewRotation {
  x: number;
  y: number;
}

interface DragState {
  pointerId: number;
  clientX: number;
  clientY: number;
}

export function StructureViewerPanel({ task, report }: StructureViewerPanelProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const structurePath = report?.structure_pdb_path ?? task?.design_result?.structure_pdb_path ?? null;
  const structureUrl = task ? `/tasks/${encodeURIComponent(task.id)}/structure` : null;
  const [source, setSource] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rotation, setRotation] = useState<ViewRotation>({ x: -0.35, y: 0.55 });

  useEffect(() => {
    let cancelled = false;
    setSource("");
    setError(null);
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

  const atoms = useMemo(() => parsePdbBackbone(source), [source]);
  const atomCount = useMemo(() => countPdbAtoms(source), [source]);
  const residueCount = useMemo(() => countResidues(atoms), [atoms]);

  useEffect(() => {
    renderStructure(canvasRef.current, atoms, rotation);
  }, [atoms, rotation]);

  function handlePointerDown(event: PointerEvent<HTMLCanvasElement>) {
    dragRef.current = {
      pointerId: event.pointerId,
      clientX: event.clientX,
      clientY: event.clientY,
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
    dragRef.current = { ...drag, clientX: event.clientX, clientY: event.clientY };
    setRotation((current) => ({
      x: current.x + dy * 0.01,
      y: current.y + dx * 0.01,
    }));
  }

  function handlePointerEnd(event: PointerEvent<HTMLCanvasElement>) {
    if (dragRef.current?.pointerId === event.pointerId) {
      dragRef.current = null;
    }
  }

  return (
    <section className="panel structure-viewer-panel">
      <div className="panel-header">
        <h2>Structure Viewer</h2>
        {atoms.length ? <span className="pill">{residueCount} residues</span> : null}
      </div>
      {structurePath ? (
        <div className="structure-viewer">
          <canvas
            ref={canvasRef}
            className="structure-canvas"
            aria-label="Protein structure backbone viewer"
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerEnd}
            onPointerCancel={handlePointerEnd}
          />
          <div className="structure-toolbar">
            <button
              type="button"
              title="Rotate structure left"
              onClick={() => setRotation((current) => ({ ...current, y: current.y - 0.35 }))}
            >
              Rotate left
            </button>
            <button
              type="button"
              title="Rotate structure right"
              onClick={() => setRotation((current) => ({ ...current, y: current.y + 0.35 }))}
            >
              Rotate right
            </button>
            <a className="button-link" href={structureUrl ?? "#"} target="_blank" rel="noreferrer">
              Open PDB
            </a>
          </div>
          <dl className="kv compact-kv structure-meta">
            <dt>Artifact</dt>
            <dd>{structurePath}</dd>
            <dt>Atoms</dt>
            <dd>{atomCount || "not parsed"}</dd>
            <dt>Backbone points</dt>
            <dd>{atoms.length || "not parsed"}</dd>
          </dl>
          {loading ? <p className="muted">Loading structure artifact...</p> : null}
          {error ? <p className="error-text">{error}</p> : null}
          {!loading && !error && source && atoms.length === 0 ? (
            <p className="muted">Structure file loaded, but no PDB ATOM/HETATM coordinates were parsed.</p>
          ) : null}
        </div>
      ) : (
        <p className="muted">No structure artifact is available for this task.</p>
      )}
    </section>
  );
}

function parsePdbBackbone(source: string): AtomPoint[] {
  const atoms: AtomPoint[] = [];
  const fallbackAtoms: AtomPoint[] = [];
  for (const line of source.split(/\r?\n/)) {
    if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) {
      continue;
    }
    const point = parsePdbAtomLine(line);
    if (!point) {
      continue;
    }
    fallbackAtoms.push(point);
    if (point.atomName === "CA" || point.atomName === "P") {
      atoms.push(point);
    }
  }
  return atoms.length ? atoms.slice(0, 1600) : fallbackAtoms.slice(0, 1600);
}

function parsePdbAtomLine(line: string): AtomPoint | null {
  const x = Number.parseFloat(line.slice(30, 38));
  const y = Number.parseFloat(line.slice(38, 46));
  const z = Number.parseFloat(line.slice(46, 54));
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
    return null;
  }
  return {
    serial: Number.parseInt(line.slice(6, 11).trim(), 10) || 0,
    atomName: line.slice(12, 16).trim(),
    residueName: line.slice(17, 20).trim(),
    residueSeq: line.slice(22, 26).trim(),
    chainId: line.slice(21, 22).trim(),
    x,
    y,
    z,
    element: line.slice(76, 78).trim() || line.slice(12, 13).trim(),
  };
}

function countPdbAtoms(source: string): number {
  return source
    .split(/\r?\n/)
    .filter((line) => line.startsWith("ATOM") || line.startsWith("HETATM"))
    .length;
}

function countResidues(atoms: AtomPoint[]): number {
  const residueKeys = new Set<string>();
  for (const atom of atoms) {
    residueKeys.add(`${atom.chainId}:${atom.residueName}:${atom.residueSeq}`);
  }
  return residueKeys.size;
}

function renderStructure(canvas: HTMLCanvasElement | null, atoms: AtomPoint[], rotation: ViewRotation) {
  if (!canvas) {
    return;
  }
  const rect = canvas.getBoundingClientRect();
  const cssWidth = Math.max(320, rect.width || 640);
  const cssHeight = Math.max(240, rect.height || 360);
  const pixelRatio = window.devicePixelRatio || 1;
  canvas.width = Math.floor(cssWidth * pixelRatio);
  canvas.height = Math.floor(cssHeight * pixelRatio);
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }
  ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  ctx.clearRect(0, 0, cssWidth, cssHeight);
  drawViewerBackground(ctx, cssWidth, cssHeight);

  if (!atoms.length) {
    ctx.fillStyle = "#777983";
    ctx.font = "600 13px Inter, sans-serif";
    ctx.fillText("No parsed coordinates", 18, 28);
    return;
  }

  const bounds = calculateBounds(atoms);
  const span = Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY, bounds.maxZ - bounds.minZ, 1);
  const scale = Math.min(cssWidth, cssHeight) * 0.72 / span;
  const projected = atoms.map((atom, index) => {
    const centered = {
      x: atom.x - bounds.centerX,
      y: atom.y - bounds.centerY,
      z: atom.z - bounds.centerZ,
    };
    const rotated = rotatePoint(centered, rotation);
    return {
      atom,
      index,
      x: cssWidth / 2 + rotated.x * scale,
      y: cssHeight / 2 - rotated.y * scale,
      z: rotated.z,
    };
  });

  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (let index = 1; index < projected.length; index += 1) {
    const prev = projected[index - 1];
    const current = projected[index];
    if (distance(prev.atom, current.atom) > 5.2) {
      continue;
    }
    const depth = normalizedDepth((prev.z + current.z) / 2, span);
    ctx.strokeStyle = `rgba(43, 94, 164, ${0.34 + depth * 0.34})`;
    ctx.lineWidth = 2.2 + depth * 2.8;
    ctx.beginPath();
    ctx.moveTo(prev.x, prev.y);
    ctx.lineTo(current.x, current.y);
    ctx.stroke();
  }

  for (const point of [...projected].sort((left, right) => left.z - right.z)) {
    const depth = normalizedDepth(point.z, span);
    const radius = 3.5 + depth * 3.8;
    ctx.fillStyle = atomColor(point.atom.element, depth);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.86)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
}

function drawViewerBackground(ctx: CanvasRenderingContext2D, width: number, height: number) {
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, "#f8fafc");
  gradient.addColorStop(1, "#eef2f7");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(31, 31, 35, 0.08)";
  ctx.lineWidth = 1;
  for (let x = 24; x < width; x += 36) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = 24; y < height; y += 36) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
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
  return Math.max(0, Math.min(1, (z / span) + 0.5));
}

function distance(left: AtomPoint, right: AtomPoint): number {
  return Math.hypot(left.x - right.x, left.y - right.y, left.z - right.z);
}

function atomColor(element: string, depth: number): string {
  const alpha = 0.72 + depth * 0.22;
  switch (element.toUpperCase()) {
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
