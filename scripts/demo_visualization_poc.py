from __future__ import annotations

import argparse
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
    import json

    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Wrote metrics -> {metrics_path}")


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
    pdb_path = download_1crn_pdb(output_path, force=args.force)
    metrics = compute_pdb_metrics(pdb_path)
    write_metrics(metrics_path, metrics)


if __name__ == "__main__":
    main()
