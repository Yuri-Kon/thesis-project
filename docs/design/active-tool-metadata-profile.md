# 当前在用工具的成本与风险元数据规范
<!-- SID:tools.metadata.active_profile -->

## 1. 文档目的
<!-- SID:tools.metadata.scope -->

本文档为当前已经投入使用的工具建立统一、可解释、可复现的元数据规范，用于：

- 静态候选排序
- `runtime_adjustment`
- `expected_remaining_cost`
- 风险与恢复复杂度估计
- 实验分组公平性控制

本规范只覆盖当前已投入使用或已进入主恢复路径的工具，不追求一次性覆盖全部候选工具。

## 2. 元数据字段
<!-- SID:tools.metadata.schema -->

每个工具应至少具备以下字段，均标准化到 `[0, 1]`：

- `compute_cost_prior`
- `latency_cost_prior`
- `failure_impact_prior`
- `human_dependency_prior`
- `reliability_prior`
- `structural_risk_prior`
- `execution_risk_prior`
- `safety_risk_prior`
- `coupling_risk_prior`
- `high_cost_flag`
- `evidence_role`
  - `cheap_validation`
  - `core_generation`
  - `high_cost_projection`
  - `refinement`
  - `objective_scoring`

## 3. 赋值原则
<!-- SID:tools.metadata.assignment_principles -->

### 3.1 成本先验

- 本地轻量解析、QC、规则打分：`0.10 ~ 0.30`
- 单次远程或 GPU 结构预测：`0.55 ~ 0.80`
- 迭代式精修、远程大模型结构映射：`0.70 ~ 0.90`

### 3.2 风险先验

- 与结构质量直接相关的工具，`structural_risk_prior` 不应过低
- 对外部网络、队列或配额敏感的工具，`execution_risk_prior` 上调
- 需要凭证、远程服务或多组件协同的工具，`coupling_risk_prior` 上调

### 3.3 可靠性先验

`reliability_prior` 表示在当前项目环境中的经验稳定性，不等同于论文中的普适稳定性。

赋值优先级：

1. 现有真实运行与集成测试经验
2. 本地/远程依赖复杂度
3. 是否存在成熟 fallback

## 4. 当前在用工具元数据表
<!-- SID:tools.metadata.active_table -->

| tool_id | capability_id | compute_cost_prior | latency_cost_prior | failure_impact_prior | human_dependency_prior | reliability_prior | structural_risk_prior | execution_risk_prior | safety_risk_prior | coupling_risk_prior | high_cost_flag | evidence_role | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `protgpt2` | `sequence_generation` | 0.45 | 0.45 | 0.40 | 0.25 | 0.62 | 0.25 | 0.38 | 0.10 | 0.30 | no | `core_generation` | 初始序列生成，成本中等，结果波动主要体现在后续结构映射。 |
| `protein_mpnn` | `sequence_design` | 0.72 | 0.62 | 0.58 | 0.28 | 0.66 | 0.32 | 0.34 | 0.10 | 0.28 | yes | `refinement` | 结构条件精修，属于高代价且可能多轮迭代的工具。 |
| `esmfold` | `structure_prediction` | 0.70 | 0.58 | 0.72 | 0.20 | 0.76 | 0.62 | 0.25 | 0.10 | 0.18 | yes | `high_cost_projection` | 本地结构预测，高代价但依赖链相对短。 |
| `nim_esmfold` | `structure_prediction` | 0.60 | 0.72 | 0.74 | 0.25 | 0.68 | 0.62 | 0.42 | 0.14 | 0.40 | yes | `high_cost_projection` | 远程结构预测，网络与配额带来更高执行与耦合风险。 |
| `openfold` | `structure_prediction` | 0.82 | 0.78 | 0.80 | 0.30 | 0.58 | 0.60 | 0.46 | 0.12 | 0.42 | yes | `high_cost_projection` | 更重的结构预测路径，应默认视为高暴露工具。 |
| `biopython_qc` | `quality_qc` | 0.12 | 0.12 | 0.30 | 0.08 | 0.90 | 0.18 | 0.10 | 0.06 | 0.08 | no | `cheap_validation` | 低成本质量门禁，是 evidence layer 的核心工具。 |
| `dssp` | `quality_qc` / `secondary_structure_annotation` | 0.22 | 0.20 | 0.35 | 0.10 | 0.82 | 0.20 | 0.16 | 0.06 | 0.12 | no | `cheap_validation` | 二级结构与质量补充，适合作为低成本验证和 fallback。 |
| `objective_ranker` | `objective_scoring` | 0.28 | 0.24 | 0.44 | 0.12 | 0.84 | 0.18 | 0.14 | 0.06 | 0.12 | no | `objective_scoring` | 中低成本打分器，主要风险在目标偏差与分数不稳定。 |

## 5. 衍生量定义
<!-- SID:tools.metadata.derived_metrics -->

### 5.1 单步标准成本

`step_cost = 0.40 * compute_cost_prior + 0.25 * latency_cost_prior + 0.20 * failure_impact_prior + 0.15 * human_dependency_prior`

### 5.2 单步标准风险

`step_risk = 0.45 * structural_risk_prior + 0.25 * execution_risk_prior + 0.20 * safety_risk_prior + 0.10 * coupling_risk_prior`

### 5.3 低成本证据层

满足以下条件的工具可被视为“证据层工具”：

- `high_cost_flag = no`
- `evidence_role = cheap_validation`
- `step_cost <= 0.25`

当前明确属于证据层的工具：

- `biopython_qc`
- `dssp`

## 6. 使用规则
<!-- SID:tools.metadata.usage_rules -->

### 6.1 规划层

- `high_cost_flag = yes` 的工具不得在证据不足时被连续串接过深
- 在存在低成本验证替代层时，应优先插入证据层再进入高代价步骤

### 6.2 恢复层

- `failure_impact_prior` 高的工具失败后，应优先考虑是否转为 `suffix_replan`
- `reliability_prior` 明显更高的同能力工具可作为 `tool_swap` 的优先 patch 候选

### 6.3 实验层

- 横向对比必须对齐工具白名单
- `high_cost_flag` 分布应记录进实验配置，避免不同组高代价暴露不公平

## 7. 后续扩展

后续可在不破坏当前字段语义的前提下增加：

- `observed_latency_p50`
- `observed_latency_p95`
- `quota_sensitivity`
- `artifact_reusability`
- `manual_salvageability`

但第一版不要求这些字段进入算法主循环。
