import type { TaskRecord } from "../api/types";

interface StructureViewerPanelProps {
  task: TaskRecord | null;
}

export function StructureViewerPanel({ task }: StructureViewerPanelProps) {
  const pdbPath = task?.design_result?.structure_pdb_path ?? null;
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Structure Viewer</h2>
      </div>
      {pdbPath ? (
        <div className="structure-placeholder">
          <strong>PDB artifact</strong>
          <a href={pdbPath}>{pdbPath}</a>
          <p className="muted">3D viewer can attach here; the PDB link remains available as fallback.</p>
        </div>
      ) : (
        <p className="muted">No structure artifact is available for this task.</p>
      )}
    </section>
  );
}
