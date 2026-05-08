# De Novo 蛋白设计报告

## 任务概览

- **任务 ID**: `issue172-live-qwen-flash-tunnel-r1_E2_high_solubility_r01`
- **设计目标**: Favor high-solubility sequence candidates under mild constraints.

External baseline style hint: Use a Reflexion-style recovery baseline. Prefer a simple initial plan but allow one text-based recovery cycle after failure feedback.
- **任务类型**: de_novo_design
- **生成时间**: 2026-04-22T03:54:30+00:00
- **执行状态**: ✅ success

## 工具链

**执行链路**: 序列设计(protgpt2) → 结构预测(openfold)

## 执行步骤

### S1: protgpt2 ✅

**输入**:
- `goal`: Favor high-solubility sequence candidates under mild constraints.Target length: 35-75 residues.
- `length_range`: [35, 75]
- `prompt`: Favor high-solubility sequence candidates under mild constraints.
- `task_id`: issue172-live-qwen-flash-tunnel-r1_E2_high_solubility_r01
- `step_id`: S1

**输出**:
- `sequence`: FAVRHIGHSLILITYSEQEN...TRTPRPASRRPSRRPRTTSS (385 aa)
- `device_used`: cuda

### S2: openfold ✅

**输入**:
- `sequence`: FAVRHIGHSLILITYSEQENCECANDIDATESNDERMILDCNSTRAINTS... (385 chars)
- `goal`: Favor high-solubility sequence candidates under mi... (230 chars)
- `length_range`: [35, 75]
- `prompt`: Favor high-solubility sequence candidates under mild constraints.
- `execution_mode`: openfold3_rest
- `task_id`: issue172-live-qwen-flash-tunnel-r1_E2_high_solubility_r01
- `step_id`: S2

**输出**:
- `pdb_path`: /home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_2746317213/openfold3_request_seed_2746317213_sample_1_model.cif
- `plddt`: 42.0
- `cif_path`: /home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_2746317213/openfold3_request_seed_2746317213_sample_1_model.cif
- `sequence`: FAVRHIGHSLILITYSEQEN...TRTPRPASRRPSRRPRTTSS (385 aa)
- `metrics`:
  - `plddt_mean`: 42.0
  - `confidence`: low
- `stage_id`: S2

### S3: biopython_qc ✅

**输入**:
- `sequence`: FAVRHIGHSLILITYSEQENCECANDIDATESNDERMILDCNSTRAINTS... (385 chars)
- `pdb_path`: /home/yurikon/Documents/thesis/thesis-project.dev/... (147 chars)
- `task_id`: issue172-live-qwen-flash-tunnel-r1_E2_high_solubility_r01
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
- `sequence`: FAVRHIGHSLILITYSEQEN...TRTPRPASRRPSRRPRTTSS (385 aa)
- `pdb_path`: /home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_2746317213/openfold3_request_seed_2746317213_sample_1_model.cif

## 设计结果

- **设计序列**: `FAVRHIGHSLILITYSEQENCECANDIDAT...ASTPPTGCSATRTPRPASRRPSRRPRTTSS`
- **序列长度**: 385 aa
- **结构文件**: `/home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_2746317213/openfold3_request_seed_2746317213_sample_1_model.cif`
- **pLDDT 均值**: 42.00
- **置信度等级**: low

---
*此报告由 SummarizerAgent 自动生成*