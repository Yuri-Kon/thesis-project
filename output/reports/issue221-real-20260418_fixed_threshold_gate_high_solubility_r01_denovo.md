# De Novo 蛋白设计报告

## 任务概览

- **任务 ID**: `issue221-real-20260418_fixed_threshold_gate_high_solubility_r01`
- **设计目标**: de_novo_design
- **任务类型**: de_novo_design
- **生成时间**: 2026-04-18T03:28:38+00:00
- **执行状态**: ✅ success

## 工具链

**执行链路**: 序列设计(protgpt2) → 结构预测(openfold)

## 执行步骤

### S1: protgpt2 ✅

**输入**:
- `goal`: de_novo_design
- `length_range`: [35, 75]
- `prompt`: Favor high-solubility sequence candidates under mild constraints.
- `task_id`: issue221-real-20260418_fixed_threshold_gate_high_solubility_r01
- `step_id`: S1

**输出**:
- `sequence`: FAVRHIGHSLILITYSEQEN...TICPTRGHPVQRASWLATSS (243 aa)
- `device_used`: cuda

### S2: openfold ✅

**输入**:
- `sequence`: FAVRHIGHSLILITYSEQENCECANDIDATESNDERMILDCNSTRAINTS... (243 chars)
- `goal`: de_novo_design
- `length_range`: [35, 75]
- `prompt`: Favor high-solubility sequence candidates under mild constraints.
- `execution_mode`: openfold3_rest
- `task_id`: issue221-real-20260418_fixed_threshold_gate_high_solubility_r01
- `step_id`: S2

**输出**:
- `pdb_path`: /home/yurikon/文档/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_42/openfold3_request_seed_42_sample_1_model.cif
- `plddt`: 42.0
- `cif_path`: /home/yurikon/文档/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_42/openfold3_request_seed_42_sample_1_model.cif
- `sequence`: FAVRHIGHSLILITYSEQEN...TICPTRGHPVQRASWLATSS (243 aa)
- `metrics`:
  - `plddt_mean`: 42.0
  - `confidence`: low
- `stage_id`: S2

### S3: biopython_qc ✅

**输入**:
- `sequence`: FAVRHIGHSLILITYSEQENCECANDIDATESNDERMILDCNSTRAINTS... (243 chars)
- `pdb_path`: /home/yurikon/文档/thesis/thesis-project.dev/output/... (124 chars)
- `task_id`: issue221-real-20260418_fixed_threshold_gate_high_solubility_r01
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
- `sequence`: FAVRHIGHSLILITYSEQEN...TICPTRGHPVQRASWLATSS (243 aa)
- `pdb_path`: /home/yurikon/文档/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_42/openfold3_request_seed_42_sample_1_model.cif

### S4: objective_ranker ✅

**输入**:
- `candidates`: [{'sequence': 'FAVRHIGHSLILITYSEQENCECANDIDATESNDERMILDCNSTRAINTSANGANPMQFASGQNYDANGNVITQQRVAAGLQYLSKPLSTGRAKPRKCRRRLHHWFIQCLHPSERVHRHRPILHPEQPPPRVSPRPTFRWWGIWERSLSRPSSVRQMAPPRSARSHSRRPYLWVAQTTSRRTTAMRNSGSTTAALRRSKTWAAPGMTTPGLPKSPISHRLTDRTICPTRGHPVQRASWLATSS', 'score': -5.782286}, {'sequence': 'FAVRHIGHSLILITYSEQENCECANDIDATESNDERMILDCNSTRAINTSANGYQAARPAANRIVWPNYPRARWGHQVRPARHRSAGYHQHFRGVAARQLDDAARIYVARTARQMRRDGAAAVAGGSI', 'score': None}, {'sequence': 'FAVRHIGHSLILITYSEQENCECANDIDATESNDERMILDCNSTRAINTSANGVNYGNGSPMPGPQPRCRPPSRPTWRASPSSPSRKPA', 'score': None}, {'sequence': 'FAVRHIGHSLILITYSEQENCECANDIDATESNDERMILDCNSTRAINTSANGMNGQFYQCIRPNGMTWAPQFQHYSQMLAQLQQTIQPILSMRPYQVSPMV', 'score': None}]
- `task_id`: issue221-real-20260418_fixed_threshold_gate_high_solubility_r01
- `step_id`: S4

**输出**:
- `tool_id`: objective_ranker
- `capability_id`: objective_scoring
- `io_type`: candidates_to_objective_scores_topk
- `default_recommendation`: candidate_1
- `objective_score`: 0.485
- `objective_explanation`: objective_ranker combined quality, novelty, stability, function, and docking proxy signals.
- `explanation`: objective_ranker combined quality, novelty, stability, function, and docking proxy signals.
- `candidate_count`: 4
- `input_candidate_count`: 4

## 设计结果

- **设计序列**: `FAVRHIGHSLILITYSEQENCECANDIDAT...SPISHRLTDRTICPTRGHPVQRASWLATSS`
- **序列长度**: 243 aa
- **结构文件**: `/home/yurikon/文档/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_42/openfold3_request_seed_42_sample_1_model.cif`
- **pLDDT 均值**: 42.00
- **置信度等级**: low

---
*此报告由 SummarizerAgent 自动生成*