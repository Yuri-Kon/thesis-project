# SFT/QLoRA Baseline Runbook

## 目标

基于冻结的 Week11 数据集跑通一次可复现的 SFT 基线训练，并导出 RC Gate-A 所需的发布级模型包元数据。

## 配置

- 仅 P0：`configs/training/sft_qlora_baseline_p0_only.json`
- P0 + P1：`configs/training/sft_qlora_baseline_p0_p1.json`

两套配置均冻结：

- 基座模型
- LoRA 超参数
- batch size / learning rate / seed
- 候选版本命名（`v0.3.0-rc1`）

## 运行命令

```bash
uv run --with torch==2.8.0 --with transformers==4.57.0 --with peft==0.17.1 --with accelerate==1.11.0 --with datasets==4.3.0 --with bitsandbytes==0.48.1 \
  python scripts/run_sft_qlora_baseline.py \
  --config configs/training/sft_qlora_baseline_p0_only.json
```

可选对照运行：

```bash
uv run --with torch==2.8.0 --with transformers==4.57.0 --with peft==0.17.1 --with accelerate==1.11.0 --with datasets==4.3.0 --with bitsandbytes==0.48.1 \
  python scripts/run_sft_qlora_baseline.py \
  --config configs/training/sft_qlora_baseline_p0_p1.json
```

## 输出结构

`output/training/w12-issue-148/<candidate_version>/<run_id>/`

- `model/` 适配器与 tokenizer 文件
- `model_package_manifest.json`
- `model_package_checksums.sha256`
- `model_card.md`
- `training_summary.json`
- `logs/trainer_log_history.json`
- `logs/smoke_inference.json`

## 验收映射

- 训练可复现：
  - 固定配置 JSON + 明确命令
  - `training_summary.json.reproducibility`
- 模型可加载 + 冒烟推理：
  - 脚本会回载 adapter 并写出 `logs/smoke_inference.json`
- 超参数与环境记录完整：
  - `training_summary.json.training`
  - `training_summary.json.environment`
- RC Gate-A 产物：
  - 模型包清单 + checksum
  - 含数据集版本、工具覆盖与已知限制的 model card
  - 输出路径中包含候选版本命名（`v0.3.0-rc1`）

## Requirement-2 并入检查

- 基于工具优先级的分层采样参数（`sampling.allowed_priorities`）
- 两套最小配置：P0-only 与 P0+P1
- 按工具切片指标输出在 `training_summary.json.tool_slice_stats`
- `model_card.md` 记录工具覆盖
