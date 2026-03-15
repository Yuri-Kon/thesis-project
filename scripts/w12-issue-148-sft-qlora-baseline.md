# W12 Issue #148: SFT/QLoRA Baseline Training

## Goal

Run one reproducible baseline SFT training from the frozen Week11 dataset, and export release-ready model package metadata for RC Gate-A.

## Configs

- P0 only: `configs/training/w12_issue148_sft_qlora_p0_only.json`
- P0 + P1: `configs/training/w12_issue148_sft_qlora_p0_p1.json`

Both configs freeze:

- base model
- LoRA hyper-parameters
- batch size / learning rate / seed
- candidate version naming (`v0.3.0-rc1`)

## Run Command

```bash
uv run --with torch==2.8.0 --with transformers==4.57.0 --with peft==0.17.1 --with accelerate==1.11.0 --with datasets==4.3.0 --with bitsandbytes==0.48.1 \
  python scripts/run_w12_issue148_sft_qlora.py \
  --config configs/training/w12_issue148_sft_qlora_p0_only.json
```

Optional comparison run:

```bash
uv run --with torch==2.8.0 --with transformers==4.57.0 --with peft==0.17.1 --with accelerate==1.11.0 --with datasets==4.3.0 --with bitsandbytes==0.48.1 \
  python scripts/run_w12_issue148_sft_qlora.py \
  --config configs/training/w12_issue148_sft_qlora_p0_p1.json
```

## Output Structure

`output/training/w12-issue-148/<candidate_version>/<run_id>/`

- `model/` adapter + tokenizer files
- `model_package_manifest.json`
- `model_package_checksums.sha256`
- `model_card.md`
- `training_summary.json`
- `logs/trainer_log_history.json`
- `logs/smoke_inference.json`

## Acceptance Mapping

- Training reproducible:
  - fixed config JSON + explicit command
  - `training_summary.json.reproducibility`
- Model load + smoke inference:
  - script reloads adapter and writes `logs/smoke_inference.json`
- Full hyper-parameter and environment record:
  - `training_summary.json.training`
  - `training_summary.json.environment`
- RC Gate-A artifacts:
  - model package manifest + checksum
  - model card with dataset version, tool coverage, known limits
  - candidate version naming in output path (`v0.3.0-rc1`)

## Requirement-2 Merge Checks

- stratified sampling config by tool priority (`sampling.allowed_priorities`)
- two minimal configs: P0-only vs P0+P1
- per-tool slice metrics exported in `training_summary.json.tool_slice_stats`
- tool coverage documented in `model_card.md`
