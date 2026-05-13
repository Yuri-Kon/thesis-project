# De Novo 蛋白设计报告

## 任务概览

- **任务 ID**: `issue172-live-minimax-m27-tunnel-r3_E0_enzyme_like_fold_r01`
- **设计目标**: Design a compact enzyme-like fold with stable core.

External baseline style hint: Use a ReAct-style single trajectory baseline. Keep one concise tool path and avoid branch search or verbal reflection.
- **任务类型**: de_novo_design
- **生成时间**: 2026-04-22T01:36:04+00:00
- **执行状态**: ✅ success

## 工具链

**执行链路**: 序列设计(protgpt2) → 结构预测(openfold)

## 执行步骤

### S1: protgpt2 ✅

**输入**:
- `goal`: Design a compact enzyme-like fold with stable core... (187 chars)
- `length_range`: [40, 80]
- `prompt`: Design a compact enzyme-like fold with stable core.
- `task_id`: issue172-live-minimax-m27-tunnel-r3_E0_enzyme_like_fold_r01
- `step_id`: S1

**输出**:
- `sequence`: DESIGNACMPACTENYMELI...AAPAAAPMMGAAADPNAPKK (123 aa)
- `device_used`: cuda

### S2: openfold ✅

**输入**:
- `sequence`: DESIGNACMPACTENYMELIKEFLDWITHSTALECREANGVGQNPMDFAN... (123 chars)
- `goal`: Design a compact enzyme-like fold with stable core... (201 chars)
- `length_range`: [40, 80]
- `prompt`: Design a compact enzyme-like fold with stable core.
- `execution_mode`: openfold3_rest
- `task_id`: issue172-live-minimax-m27-tunnel-r3_E0_enzyme_like_fold_r01
- `step_id`: S2

**输出**:
- `pdb_path`: /home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_2746317213/openfold3_request_seed_2746317213_sample_1_model.cif
- `plddt`: 42.0
- `cif_path`: /home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_2746317213/openfold3_request_seed_2746317213_sample_1_model.cif
- `sequence`: DESIGNACMPACTENYMELI...AAPAAAPMMGAAADPNAPKK (123 aa)
- `metrics`:
  - `plddt_mean`: 42.0
  - `confidence`: low
- `stage_id`: S2

### S3: biopython_qc ✅

**输入**:
- `pdb_path`: /home/yurikon/Documents/thesis/thesis-project.dev/... (147 chars)
- `sequence`: DESIGNACMPACTENYMELIKEFLDWITHSTALECREANGVGQNPMDFAN... (123 chars)
- `task_id`: issue172-live-minimax-m27-tunnel-r3_E0_enzyme_like_fold_r01
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
- `sequence`: DESIGNACMPACTENYMELI...AAPAAAPMMGAAADPNAPKK (123 aa)
- `pdb_path`: /home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_2746317213/openfold3_request_seed_2746317213_sample_1_model.cif

## 设计结果

- **设计序列**: `DESIGNACMPACTENYMELIKEFLDWITHS...VAAAVAAAEAAAPAAAPMMGAAADPNAPKK`
- **序列长度**: 123 aa
- **结构文件**: `/home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_2746317213/openfold3_request_seed_2746317213_sample_1_model.cif`
- **pLDDT 均值**: 42.00
- **置信度等级**: low

---
*此报告由 SummarizerAgent 自动生成*