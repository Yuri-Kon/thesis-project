from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.request import urlopen

try:
    from Bio.PDB import PDBParser
    from Bio.PDB.Polypeptide import is_aa
except ImportError as exc:
    raise SystemExit(
        "BioPython is required for PDB parsing. Install it via `pip install biopython`."
    ) from exc

RCSB_BASE_URL = "https://files.rcsb.org/download"
PDB_ID = "1CRN"
PDB_FILENAME = "1crn.pdb"


def build_pdb_url(pdb_id: str) -> str:
    return f"{RCSB_BASE_URL}/{pdb_id.upper()}.pdb"


def download_1crn_pdb(output_path: Path, force: bool = False) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not force:
        print(f"Skip download; file exists: {output_path}")
        return output_path

    url = build_pdb_url(PDB_ID)
    with urlopen(url) as response:
        status = response.getcode()
        if status is not None and status >= 400:
            raise RuntimeError(f"Download failed ({status}): {url}")
        data = response.read()

    output_path.write_bytes(data)
    print(f"Downloaded {url} -> {output_path}")
    return output_path


def compute_pdb_metrics(pdb_path: Path) -> dict[str, Any]:
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure(PDB_ID, str(pdb_path))

    chain_ids = []
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
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Wrote metrics -> {metrics_path}")


def build_plotly_snippet(
    per_residue: list[dict[str, Any]],
    div_id: str = "bfactor-chart",
    include_lib: bool = True,
) -> str:
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
            "  title: '1CRN B-factor Average per Residue',",
            "  xaxis: {title: 'Residue Index'},",
            "  yaxis: {title: 'B-factor Average'},",
            "  margin: {l: 60, r: 20, t: 50, b: 50},",
            "};",
            f"Plotly.newPlot('{div_id}', [trace], layout, {{displayModeBar: false}});",
            "</script>",
        ]
    )
    return "\n".join(lines)


def write_plotly_html(metrics_path: Path, html_path: Path) -> None:
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    per_residue = metrics.get("per_residue_bfactor_avg", [])
    snippet = build_plotly_snippet(per_residue, include_lib=True)

    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(
        snippet,
        encoding="utf-8",
    )
    print(f"Wrote Plotly HTML -> {html_path}")


def write_report_html(
    report_path: Path,
    metrics: dict[str, Any],
    plotly_snippet: str,
    pdb_rel_path: str,
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
            "  <title>1CRN Demo Report</title>",
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
            "    <h1>1CRN Demo Report</h1>",
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
    print(f"Wrote report HTML -> {report_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download 1CRN PDB into output/demo/pdb/1crn.pdb",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing file if present.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output_path = repo_root / "output" / "demo" / "pdb" / PDB_FILENAME
    metrics_path = repo_root / "output" / "demo" / "metrics.json"
    plotly_path = repo_root / "output" / "demo" / "plotly.html"
    report_path = repo_root / "output" / "demo" / "report.html"
    pdb_path = download_1crn_pdb(output_path, force=args.force)
    metrics = compute_pdb_metrics(pdb_path)
    write_metrics(metrics_path, metrics)
    write_plotly_html(metrics_path, plotly_path)
    plotly_snippet = build_plotly_snippet(
        metrics.get("per_residue_bfactor_avg", []),
        include_lib=False,
    )
    write_report_html(report_path, metrics, plotly_snippet, "pdb/1crn.pdb")


if __name__ == "__main__":
    main()
