from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

RCSB_BASE_URL = "https://files.rcsb.org/download"


class VisualizationError(RuntimeError):
    """Base error for visualization pipeline failures."""


class PdbDownloadError(VisualizationError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class VisualizationArtifacts:
    metrics_json_path: Path
    plotly_html_path: Path
    report_html_path: Path
    assets_dir: Path
    pdb_path: Path
    summary_stats: dict[str, Any]


def run_visualization(
    pdb_ref: str,
    out_dir: Path,
    *,
    reuse_cache: bool = True,
) -> VisualizationArtifacts:
    out_dir = Path(out_dir)
    assets_dir = out_dir / "pdb"
    pdb_path = _prepare_pdb_asset(pdb_ref, assets_dir, reuse_cache=reuse_cache)

    metrics = compute_pdb_metrics(pdb_path)
    pdb_label = _derive_pdb_label(pdb_ref, pdb_path)
    metrics_path = out_dir / "metrics.json"
    plotly_path = out_dir / "plotly.html"
    report_path = out_dir / "report.html"

    write_metrics(metrics_path, metrics)
    plotly_snippet = build_plotly_snippet(
        metrics.get("per_residue_bfactor_avg", []),
        title=f"{pdb_label} B-factor Average per Residue",
        include_lib=True,
    )
    write_plotly_html(plotly_path, plotly_snippet)

    report_plotly_snippet = build_plotly_snippet(
        metrics.get("per_residue_bfactor_avg", []),
        title=f"{pdb_label} B-factor Average per Residue",
        include_lib=False,
    )
    pdb_rel_path = f"pdb/{pdb_path.name}"
    write_report_html(
        report_path,
        metrics,
        report_plotly_snippet,
        pdb_rel_path,
        pdb_label,
    )

    summary_stats = {
        "residue_count": metrics.get("residue_count"),
        "chain_ids": metrics.get("chain_ids"),
    }

    return VisualizationArtifacts(
        metrics_json_path=metrics_path,
        plotly_html_path=plotly_path,
        report_html_path=report_path,
        assets_dir=assets_dir,
        pdb_path=pdb_path,
        summary_stats=summary_stats,
    )


def build_pdb_url(pdb_id: str) -> str:
    return f"{RCSB_BASE_URL}/{pdb_id.upper()}.pdb"


def _prepare_pdb_asset(pdb_ref: str, assets_dir: Path, *, reuse_cache: bool) -> Path:
    assets_dir.mkdir(parents=True, exist_ok=True)
    pdb_path = Path(pdb_ref)
    if pdb_path.exists():
        return _copy_pdb_to_assets(pdb_path, assets_dir, reuse_cache=reuse_cache)

    if pdb_ref.lower().endswith(".pdb"):
        raise FileNotFoundError(f"PDB file not found: {pdb_ref}")

    return _download_pdb_to_assets(pdb_ref, assets_dir, reuse_cache=reuse_cache)


def _derive_pdb_label(pdb_ref: str, pdb_path: Path) -> str:
    pdb_path = Path(pdb_path)
    if pdb_ref and not pdb_ref.lower().endswith(".pdb"):
        return pdb_ref.upper()
    if pdb_path.stem:
        return pdb_path.stem.upper()
    return "PDB"


def _copy_pdb_to_assets(
    source_path: Path,
    assets_dir: Path,
    *,
    reuse_cache: bool,
) -> Path:
    if not source_path.exists():
        raise FileNotFoundError(f"PDB file not found: {source_path}")
    target_path = assets_dir / source_path.name
    if target_path.exists() and reuse_cache:
        return target_path
    target_path.write_bytes(source_path.read_bytes())
    return target_path


def _download_pdb_to_assets(
    pdb_id: str,
    assets_dir: Path,
    *,
    reuse_cache: bool,
) -> Path:
    pdb_filename = f"{pdb_id.lower()}.pdb"
    target_path = assets_dir / pdb_filename
    if target_path.exists() and reuse_cache:
        return target_path

    url = build_pdb_url(pdb_id)
    try:
        with urlopen(url) as response:
            status = response.getcode()
            if status is not None and status >= 400:
                raise PdbDownloadError(
                    f"Download failed ({status}): {url}",
                    retryable=False,
                )
            data = response.read()
    except HTTPError as exc:
        raise PdbDownloadError(
            f"Download failed ({exc.code}): {url}",
            retryable=False,
        ) from exc
    except URLError as exc:
        raise PdbDownloadError(
            f"Download failed (network error): {url}",
            retryable=True,
        ) from exc

    target_path.write_bytes(data)
    return target_path


def _load_biopython():
    try:
        from Bio.PDB import PDBParser
        from Bio.PDB.Polypeptide import is_aa
    except ImportError as exc:
        raise RuntimeError(
            "BioPython is required for PDB parsing. Install it via `pip install biopython`."
        ) from exc
    return PDBParser, is_aa


def compute_pdb_metrics(pdb_path: Path) -> dict[str, Any]:
    parser_cls, is_aa = _load_biopython()
    parser = parser_cls(QUIET=True)
    structure = parser.get_structure("structure", str(pdb_path))

    chain_ids: list[str] = []
    residue_count = 0
    per_residue_bfactor_avg = []

    for model in structure:
        for chain in model:
            chain_id = chain.id
            if chain_id not in chain_ids:
                chain_ids.append(chain_id)
            for residue in chain:
                if not is_aa(residue, standard=True):
                    continue
                residue_count += 1
                atom_bfactors = [atom.get_bfactor() for atom in residue.get_atoms()]
                bfactor_avg = (
                    sum(atom_bfactors) / len(atom_bfactors) if atom_bfactors else 0.0
                )
                per_residue_bfactor_avg.append(
                    {
                        "res_index": residue.id[1],
                        "res_id": residue.resname,
                        "chain_id": chain_id,
                        "bfactor_avg": bfactor_avg,
                    }
                )

    return {
        "chain_ids": chain_ids,
        "residue_count": residue_count,
        "per_residue_bfactor_avg": per_residue_bfactor_avg,
    }


def write_metrics(metrics_path: Path, metrics: dict[str, Any]) -> None:
    import json

    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def build_plotly_snippet(
    per_residue: list[dict[str, Any]],
    *,
    div_id: str = "bfactor-chart",
    title: str = "B-factor Average per Residue",
    include_lib: bool = True,
) -> str:
    import json

    x_values = [item["res_index"] for item in per_residue]
    y_values = [item["bfactor_avg"] for item in per_residue]

    lines = [
        f'<div id="{div_id}" style="width: 100%; height: 420px;"></div>',
    ]
    if include_lib:
        lines.append('<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>')
    lines.extend(
        [
            "<script>",
            "const trace = {",
            f"  x: {json.dumps(x_values)},",
            f"  y: {json.dumps(y_values)},",
            "  mode: 'lines',",
            "  line: {color: '#1f77b4'},",
            "};",
            "const layout = {",
            f"  title: {json.dumps(title)},",
            "  xaxis: {title: 'Residue Index'},",
            "  yaxis: {title: 'B-factor Average'},",
            "  margin: {l: 60, r: 20, t: 50, b: 50},",
            "};",
            f"Plotly.newPlot('{div_id}', [trace], layout, {{displayModeBar: false}});",
            "</script>",
        ]
    )
    return "\n".join(lines)


def write_plotly_html(plotly_path: Path, snippet: str) -> None:
    plotly_path.parent.mkdir(parents=True, exist_ok=True)
    plotly_path.write_text(snippet, encoding="utf-8")


def write_report_html(
    report_path: Path,
    metrics: dict[str, Any],
    plotly_snippet: str,
    pdb_rel_path: str,
    pdb_label: str,
) -> None:
    chain_ids = metrics.get("chain_ids", [])
    residue_count = metrics.get("residue_count", 0)
    chain_label = ", ".join(chain_ids) if chain_ids else "N/A"

    html = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8" />',
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />",
            f"  <title>{pdb_label} Demo Report</title>",
            "  <script src=\"https://cdn.plot.ly/plotly-2.27.0.min.js\"></script>",
            "  <script src=\"https://cdn.jsdelivr.net/npm/ngl@2.0.0-dev.39/dist/ngl.js\"></script>",
            "  <style>",
            "    body { font-family: Arial, sans-serif; margin: 0; background: #f6f7fb; color: #1d1f27; }",
            "    main { max-width: 1080px; margin: 0 auto; padding: 32px 20px 48px; }",
            "    h1 { margin: 0 0 8px; font-size: 28px; }",
            "    .summary { margin: 0 0 24px; color: #4b5563; }",
            "    section { background: #ffffff; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08); }",
            "    #ngl-viewer { width: 100%; height: 520px; background: #0f172a; }",
            "    #ngl-error { display: none; margin-top: 12px; color: #b91c1c; }",
            "  </style>",
            "</head>",
            "<body>",
            "  <main>",
            f"    <h1>{pdb_label} Demo Report</h1>",
            f"    <p class=\"summary\">Residues: {residue_count} | Chains: {chain_label}</p>",
            "    <section>",
            "      <h2>B-factor Trend</h2>",
            plotly_snippet,
            "    </section>",
            "    <section>",
            "      <h2>3D Structure</h2>",
            "      <div id=\"ngl-viewer\"></div>",
            "      <div id=\"ngl-error\"></div>",
            "    </section>",
            "  </main>",
            "  <script>",
            f"    const pdbUrl = '{pdb_rel_path}';",
            "    const errorEl = document.getElementById('ngl-error');",
            "    const showError = (message) => {",
            "      if (!errorEl) {",
            "        return;",
            "      }",
            "      errorEl.style.display = 'block';",
            "      errorEl.innerHTML = message;",
            "    };",
            "    try {",
            "      if (!window.NGL) {",
            "        showError(",
            "          `NGL failed to load from CDN. Check network access and reload. ` +",
            "            `You can also open the PDB directly: <a href=\"${pdbUrl}\">${pdbUrl}</a>`",
            "        );",
            "      } else {",
            "        const stage = new NGL.Stage('ngl-viewer', { backgroundColor: '#0f172a' });",
            "        stage.loadFile(pdbUrl, { defaultRepresentation: false }).then((component) => {",
            "          component.addRepresentation('cartoon', { color: 'sstruc' });",
            "          component.addRepresentation('ball+stick', { sele: 'not hydrogen' });",
            "          component.autoView();",
            "        }).catch(() => {",
            "          showError(",
            "            `NGL failed to load structure. Open the PDB directly: <a href=\"${pdbUrl}\">${pdbUrl}</a>`",
            "          );",
            "        });",
            "        window.addEventListener('resize', () => stage.handleResize(), false);",
            "      }",
            "    } catch (err) {",
            "      showError(",
            "        `NGL failed to initialize. Open the PDB directly: <a href=\"${pdbUrl}\">${pdbUrl}</a>`",
            "      );",
            "    }",
            "  </script>",
            "</body>",
            "</html>",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(html, encoding="utf-8")
