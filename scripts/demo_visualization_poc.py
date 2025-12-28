from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlopen

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
    download_1crn_pdb(output_path, force=args.force)


if __name__ == "__main__":
    main()
