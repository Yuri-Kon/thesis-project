# De Novo 蛋白设计报告

## 任务概览

- **任务 ID**: `issue172-live-qwen-flash-tunnel-r1_E0_enzyme_like_fold_r01`
- **设计目标**: Design a compact enzyme-like fold with stable core.

External baseline style hint: Use a ReAct-style single trajectory baseline. Keep one concise tool path and avoid branch search or verbal reflection.
- **任务类型**: de_novo_design
- **生成时间**: 2026-04-22T02:46:03+00:00
- **执行状态**: ✅ success

## 工具链

**执行链路**: 序列设计(protein_mpnn) → 结构预测(openfold)

## 执行步骤

### S1: protgpt2 ✅

**输入**:
- `goal`: Design a compact enzyme-like fold with stable core.Target length: 40-80 residues.
- `length_range`: [40, 80]
- `prompt`: Design a compact enzyme-like fold with stable core.
- `task_id`: issue172-live-qwen-flash-tunnel-r1_E0_enzyme_like_fold_r01
- `step_id`: S1

**输出**:
- `sequence`: DESIGNACMPACTENYMELI...LGYVVPANQVNPGWGQGMGL (74 aa)
- `device_used`: cuda

### S2: openfold ✅

**输入**:
- `sequence`: DESIGNACMPACTENYMELIKEFLDWITHSTALECREANGNFWNPNGVVQNPWKLGYVVPANQVNPGWGQGMGL
- `goal`: Design a compact enzyme-like fold with stable core... (201 chars)
- `length_range`: [40, 80]
- `prompt`: Design a compact enzyme-like fold with stable core.
- `execution_mode`: openfold3_rest
- `task_id`: issue172-live-qwen-flash-tunnel-r1_E0_enzyme_like_fold_r01
- `step_id`: S2

**输出**:
- `pdb_path`: /home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_2746317213/openfold3_request_seed_2746317213_sample_1_model.cif
- `plddt`: 42.0
- `cif_path`: /home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_2746317213/openfold3_request_seed_2746317213_sample_1_model.cif
- `sequence`: DESIGNACMPACTENYMELI...LGYVVPANQVNPGWGQGMGL (74 aa)
- `metrics`:
  - `plddt_mean`: 42.0
  - `confidence`: low
- `stage_id`: S2

### S3: protein_mpnn ✅

**输入**:
- `pdb_path`: /home/yurikon/Documents/thesis/thesis-project.dev/... (147 chars)
- `length_range`: [40, 80]
- `goal`: Design a compact enzyme-like fold with stable core... (201 chars)
- `num_candidates`: 5
- `task_id`: issue172-live-qwen-flash-tunnel-r1_E0_enzyme_like_fold_r01
- `step_id`: S3

**输出**:
- `sequence`: QSSIADMAGWHTVMEVYWIK...IESMWMFCKVYTNVYCHQYK (70 aa)
- `sequence_score`: 0.54431

## 设计结果

- **设计序列**: `QSSIADMAGWHTVMEVYWIKQNYLMMQEGW...YCYTEKHWHYIESMWMFCKVYTNVYCHQYK`
- **序列长度**: 70 aa
- **结构文件**: `/home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_2746317213/openfold3_request_seed_2746317213_sample_1_model.cif`
- **pLDDT 均值**: 42.00
- **置信度等级**: low

---
*此报告由 SummarizerAgent 自动生成*