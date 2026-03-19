import importlib.util
from pathlib import Path


SCRIPT_PATH = Path("scripts/smoke_test_llm_providers.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("smoke_test_llm_providers", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_run_provider_returns_missing_api_key_without_calling_provider(monkeypatch, tmp_path):
    module = _load_module()
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    config_path = tmp_path / "providers.json"
    config_path.write_text(
        """
{
  "providers": {
    "qwen-plus": {
      "provider_type": "openai_compatible",
      "model_name": "qwen-plus",
      "api_key_env": "DASHSCOPE_API_KEY"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )

    result = module.run_provider(
        alias="qwen-plus",
        catalog_path=config_path,
        goal="demo",
        target_length=32,
    )

    assert result["provider"] == "qwen-plus"
    assert result["success"] is False
    assert result["error"] == "missing_api_key:DASHSCOPE_API_KEY"


def test_run_provider_with_timeout_returns_timeout(monkeypatch, tmp_path):
    module = _load_module()
    config_path = tmp_path / "providers.json"
    config_path.write_text('{"providers": {}}', encoding="utf-8")

    def fake_worker(alias, catalog_path, goal, target_length, result_queue):
        del alias, catalog_path, goal, target_length, result_queue
        import time

        time.sleep(1.0)

    monkeypatch.setattr(module, "_provider_worker", fake_worker)

    result = module.run_provider_with_timeout(
        alias="slow-provider",
        catalog_path=config_path,
        goal="demo",
        target_length=32,
        timeout_seconds=0,
    )

    assert result["provider"] == "slow-provider"
    assert result["success"] is False
    assert result["error"] == "timeout_after:0s"
