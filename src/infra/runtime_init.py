from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.kg.kg_client import ToolKGError, load_tool_kg


@dataclass(frozen=True)
class RuntimePaths:
    """Resolved runtime paths used by demo/API bootstrap."""

    kg_path: Path
    output_dir: Path
    data_dir: Path
    log_dir: Path
    snapshot_dir: Path


@dataclass(frozen=True)
class RuntimeInitResult:
    """Initialization summary for health checks and startup logging."""

    paths: RuntimePaths
    tool_count: int


def resolve_runtime_paths(
    *,
    kg_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    data_dir: Optional[Path] = None,
    log_dir: Optional[Path] = None,
    snapshot_dir: Optional[Path] = None,
) -> RuntimePaths:
    resolved_data_dir = data_dir or Path("data")
    resolved_log_dir = log_dir or (resolved_data_dir / "logs")
    resolved_snapshot_dir = snapshot_dir or (resolved_data_dir / "snapshots")
    resolved_output_dir = output_dir or Path("output")
    resolved_kg_path = kg_path or (Path("src") / "kg" / "protein_tool_kg.json")

    return RuntimePaths(
        kg_path=resolved_kg_path,
        output_dir=resolved_output_dir,
        data_dir=resolved_data_dir,
        log_dir=resolved_log_dir,
        snapshot_dir=resolved_snapshot_dir,
    )


def initialize_runtime(
    *,
    kg_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    data_dir: Optional[Path] = None,
    log_dir: Optional[Path] = None,
    snapshot_dir: Optional[Path] = None,
) -> RuntimeInitResult:
    """Ensure runtime directories exist and ProteinToolKG is readable."""
    paths = resolve_runtime_paths(
        kg_path=kg_path,
        output_dir=output_dir,
        data_dir=data_dir,
        log_dir=log_dir,
        snapshot_dir=snapshot_dir,
    )

    paths.output_dir.mkdir(parents=True, exist_ok=True)
    paths.log_dir.mkdir(parents=True, exist_ok=True)
    paths.snapshot_dir.mkdir(parents=True, exist_ok=True)

    kg = load_tool_kg(paths.kg_path)
    tools = kg.get("tools", [])
    if not isinstance(tools, list):
        raise ToolKGError("ProteinToolKG 'tools' must be a list")

    return RuntimeInitResult(paths=paths, tool_count=len(tools))
