# De Novo 蛋白设计报告

## 任务概览

- **任务 ID**: `issue172-live-qwen-flash-tunnel-r1_E1_enzyme_like_fold_r02_attempt2`
- **设计目标**: Design a compact enzyme-like fold with stable core.

External baseline style hint: Use a ToT-style multi-branch baseline. Explore up to 3 candidate branches before selecting the most promising plan.
- **任务类型**: de_novo_design
- **生成时间**: 2026-04-22T09:25:08+00:00
- **执行状态**: ✅ success

## 工具链

**执行链路**: 序列设计(protgpt2) → 结构预测(nim_esmfold)

## 执行步骤

### S1: protgpt2 ✅

**输入**:
- `goal`: Design a compact enzyme-like fold with stable core.
- `length_range`: [40, 80]
- `prompt`: Design a compact enzyme-like fold with stable core.
- `task_id`: issue172-live-qwen-flash-tunnel-r1_E1_enzyme_like_fold_r02_attempt2
- `step_id`: S1

**输出**:
- `sequence`: DESIGNACMPACTENYMELI...EDWDSYRPMRANYAGVLGTQ (288 aa)
- `device_used`: cuda

### S2: nim_esmfold ✅

**输入**:
- `sequence`: DESIGNACMPACTENYMELIKEFLDWITHSTALECREANGRPYCTEQAFA... (288 chars)
- `task_id`: issue172-live-qwen-flash-tunnel-r1_E1_enzyme_like_fold_r02_attempt2
- `step_id`: S2

**输出**:
- `pdb_path`: /home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/nim_issue172-live-qwen-flash-tunnel-r1_E1_enzyme_like_fold_r02_attempt2_S2.pdb
- `plddt`: 28.202147019273866
- `metrics`:
  - `plddt_mean`: 28.202147019273866
  - `confidence`: low
- `stage_id`: S2

### S3: biopython_qc ✅

**输入**:
- `sequence`: DESIGNACMPACTENYMELIKEFLDWITHSTALECREANGRPYCTEQAFA... (288 chars)
- `pdb_path`: /home/yurikon/Documents/thesis/thesis-project.dev/... (139 chars)
- `task_id`: issue172-live-qwen-flash-tunnel-r1_E1_enzyme_like_fold_r02_attempt2
- `step_id`: S3

**输出**:
- `stage_id`: S3
- `stage_name`: quality_gate
- `capability_id`: quality_qc
- `io_type`: sequence_structure_to_qc_metrics
- `pass_count`: 1
- `fail_count`: 0
- `pass_fail`: True
- `best_candidate_id`: candidate_1
- `sequence`: DESIGNACMPACTENYMELI...EDWDSYRPMRANYAGVLGTQ (288 aa)
- `pdb_path`: /home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/nim_issue172-live-qwen-flash-tunnel-r1_E1_enzyme_like_fold_r02_attempt2_S2.pdb
- `plddt`: 28.202147019273866

## 设计结果

- **设计序列**: `DESIGNACMPACTENYMELIKEFLDWITHS...HYNYTDVMMPEDWDSYRPMRANYAGVLGTQ`
- **序列长度**: 288 aa
- **结构文件**: `/home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/nim_issue172-live-qwen-flash-tunnel-r1_E1_enzyme_like_fold_r02_attempt2_S2.pdb`
- **pLDDT 均值**: 28.20
- **置信度等级**: low

---
*此报告由 SummarizerAgent 自动生成*