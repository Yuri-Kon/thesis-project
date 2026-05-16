"""Quick smoke test for all configured LLM providers.

Usage:  uv run python tmp/test_providers.py [alias ...]
        uv run python tmp/test_providers.py glm-5 deepseek-v4-pro

Checks: 1) API key available  2) provider instantiated
        3) call_planner() round-trip with a minimal task
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.provider_registry import create_provider, load_provider_catalog  # noqa: E402
from src.models.contracts import ProteinDesignTask  # noqa: E402

CATALOG_PATH = PROJECT_ROOT / "configs" / "llm_providers.json"

_MINIMAL_TASK = ProteinDesignTask(
    task_id="smoke_test",
    goal="Design a stable small protein around 100 residues.",
    constraints={
        "task_kind": "de_novo_design",
        "length_range": [90, 120],
        "design_count": 1,
        "run_profile": "balanced",
        "safety_level": "S1",
    },
)


def check_provider(alias: str, settings: object) -> tuple[bool, str]:
    """Return (ok, detail)."""
    api_key_env = getattr(settings, "api_key_env", None)
    api_key = getattr(settings, "api_key", None)

    if isinstance(api_key, str) and api_key.strip():
        pass
    elif isinstance(api_key_env, str) and os.getenv(api_key_env):
        pass
    else:
        return False, f"no API key (env: {api_key_env or 'N/A'})"

    try:
        provider = create_provider(settings)
    except Exception as exc:
        return False, f"create error: {exc}"

    try:
        plan_dict = provider.call_planner(_MINIMAL_TASK, [])
        steps = len(plan_dict.get("steps", [])) if isinstance(plan_dict, dict) else 0
        return True, f"plan returned with {steps} step(s)"
    except Exception as exc:
        msg = str(exc)[:150].replace("\n", " ")
        return False, f"{msg}"


def main() -> None:
    catalog = load_provider_catalog(CATALOG_PATH)
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(catalog.providers.keys())

    ok_count = 0
    fail_count = 0
    skipped = 0

    for alias in targets:
        if alias == "baseline":
            skipped += 1
            continue
        settings = catalog.providers.get(alias)
        if settings is None:
            print(f"[MISS] {alias:20s}  not found in catalog")
            fail_count += 1
            continue

        ok, detail = check_provider(alias, settings)
        if ok:
            print(f"[OK]   {alias:20s}  {detail}")
            ok_count += 1
        else:
            print(f"[FAIL] {alias:20s}  {detail}")
            fail_count += 1

    if skipped:
        print(f"\n{ok_count} OK, {fail_count} FAIL, {skipped} skipped")
    else:
        print(f"\n{ok_count} OK, {fail_count} FAIL")


if __name__ == "__main__":
    main()
