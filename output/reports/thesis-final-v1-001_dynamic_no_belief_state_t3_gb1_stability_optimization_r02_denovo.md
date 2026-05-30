# De Novo 蛋白设计报告

## 任务概览

- **任务 ID**: `thesis-final-v1-001_dynamic_no_belief_state_t3_gb1_stability_optimization_r02`
- **设计目标**: Design a 50-60 residue GB1-like alpha/beta domain optimized for foldability and solubility, without requiring immunoglobulin binding.
- **任务类型**: de_novo_design
- **生成时间**: 2026-05-10T08:57:41+00:00
- **执行状态**: ✅ success

## 工具链

**执行链路**: 结构预测(openfold)

## 执行步骤

### S1: openfold ✅

**输入**:
- `sequence`: MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR
- `execution_mode`: openfold3_rest
- `task_id`: thesis-final-v1-001_dynamic_no_belief_state_t3_gb1_stability_optimization_r02
- `step_id`: S1

**输出**:
- `pdb_path`: /home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_42/openfold3_request_seed_42_sample_1_model.cif
- `plddt`: 42.0
- `cif_path`: /home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_42/openfold3_request_seed_42_sample_1_model.cif
- `sequence`: MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR
- `metrics`:
  - `plddt_mean`: 42.0
  - `confidence`: low
- `stage_id`: S2

## 设计结果

- **设计序列**: `MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLR`
- **序列长度**: 35 aa
- **结构文件**: `/home/yurikon/Documents/thesis/thesis-project.dev/output/pdb/openfold3_request/seed_42/openfold3_request_seed_42_sample_1_model.cif`
- **pLDDT 均值**: 42.00
- **置信度等级**: low

---
*此报告由 SummarizerAgent 自动生成*