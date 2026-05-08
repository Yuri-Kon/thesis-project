# 毕业论文最终任务集与真实案例设计

更新时间：2026-05-08

## 1. 对实验设计书的审查结论

`docs/experiment/final-thesis-experiment-design.md` 的总体设计是合理的，可以作为第五章系统测试与算法实验的主方案。它的主要优点是：

- 把系统工程验证和 CEBRA-WP 算法验证拆成两条主线，避免只用 pytest 结果替代论文实验。
- 提前限定 `lite_belief_state` 的结论边界，能够避免把成本控制或止损效果误写成最终设计质量提升。
- RQ、实验编号、指标、证据产物和最小可交付包之间有清晰映射，适合按证据链组织论文材料。
- EXP-A4 单独比较 `dynamic_observation_only` 与 `lite_belief_state`，正好补旧结果中 belief-state 增量证据不足的问题。

实际执行前建议修正或补齐以下点：

| 问题 | 影响 | 建议 |
|:---|:---|:---|
| 论文组名 `static_gate` 与代码/配置中的 `fixed_threshold_gate` 不完全一致 | 后续表格和产物聚合容易出现组名漂移 | 论文统一写“固定阈值 gate”，括号标注代码 id：`fixed_threshold_gate` |
| 文档建议新增 `thesis_final_task_set.json`，但 EXP-A2 命令仍使用旧 baseline contract 的任务 | 真实任务集不会自动进入四组矩阵 | 已新增 `configs/experiments/thesis_final_experiment_matrix.json`，并让矩阵 runner 支持 `task_set_config_path` |
| `action_agreement`、`stop_quality`、`evidence_sufficiency` 需要 oracle/rubric | 否则算法指标难以复现 | 在每个任务中显式写入 `oracle_action`、`stop_quality_rubric` 或 `expected_focus` |
| `runtime_seconds` 混合真实 provider 与 mock provider 会误导 | 真实远程服务和本地模拟成本不可比 | 结果表拆成 `mock_runtime_seconds` 与 `real_provider_runtime_seconds`，或至少在 run metadata 标注 execution mode |
| 每类至少 3 个样本、每组至少重复 3 次工作量较大 | 时间紧时可能影响论文收敛 | 主文档已有最小包策略；实际建议先跑每类 1 个样本、每组 2 次，确认链路后再扩展 |
| 高风险/安全任务需要明确边界 | 避免系统自动批准敏感 motif 或越过 HITL | 安全任务只作为 warn/block 边界测试，不做可表达、可生产的功能蛋白设计 |

结论：设计书没有方向性问题。它现在最缺的是冻结任务集、指标判定 rubric 和最终 matrix 配置的落地连接。

## 2. 真实案例来源

以下案例来自公开结构数据库，可作为毕业论文最终任务集的现实背景，不用于声明湿实验验证。

| 来源 id | 结构/案例 | 可用于 | 关键事实 |
|:---|:---|:---|:---|
| `1L2Y` | Trp-cage TC5b | 短肽 de novo、序列评估、参数失败恢复 | 20 aa，solution NMR，de novo protein；PDBe 给出链 A 序列 `NLYIQWLKDGGPSSGRPPPS` |
| `1VII` | chicken villin headpiece HP35 | 短螺旋束、稳定性优化 | 35/36 aa 级别的 thermostable subdomain，solution NMR；JenaLib 列出链 A 残基 |
| `1PGB` / `2GB1` | Protein G B1 domain | 序列评估、多约束稳定性优化 | 56 aa，紧密疏水核心，beta-sheet + alpha-helix，小型稳定结构域 |
| `1UBQ` | ubiquitin | 结构预测高置信正例、端到端评估 | 76 aa，1.8 A crystal structure，常用折叠/结构预测基准 |
| `1QYS` | Top7 | 高代价结构预测、结构性失败/重规划 | de novo protein，Top7，约 90-110 aa，2.5 A crystal structure，论文报告设计模型与晶体结构接近 |
| `5J0H` | de novo homo-oligomer design | 高风险结构复杂度、预算控制扩展样例 | synthetic construct，79 aa chain，homo 3-mer，1.64 A crystal structure |

参考链接：

- RCSB PDB 1L2Y: https://www.rcsb.org/structure/1L2Y
- PDBe 1L2Y chain sequence: https://www.ebi.ac.uk/pdbe/entry/pdb/1l2y/protein/1
- RCSB PDB 1VII: https://www.rcsb.org/structure/1VII
- JenaLib 1VII sequence listing: https://jenalib.leibniz-fli.de/cgi-bin/P/PDBscan.pl?code=1vii
- RCSB PDB 1PGB: https://www.rcsb.org/structure/1PGB
- RCSB PDB 2GB1: https://www.rcsb.org/structure/2GB1
- RCSB PDB 1UBQ: https://www.rcsb.org/structure/1UBQ
- RCSB PDB 1QYS: https://www.rcsb.org/structure/1QYS
- RCSB PDB 5J0H: https://www.rcsb.org/structure/5J0H

## 3. 最终任务样例

| task_key | 类别 | 真实背景 | 设计需求 | 预期验证点 |
|:---|:---|:---|:---|:---|
| `t1_trpcage_denovo_short_peptide` | T1 | Trp-cage TC5b / 1L2Y | 设计 18-24 aa 的单链疏水核心短肽，避免二硫键和配体依赖 | 正常规划、结构预测、报告 |
| `t1_villin_like_helix_bundle` | T1 | Villin HP35 / 1VII | 设计 32-40 aa 三螺旋小结构域，偏高螺旋比例 | 正常 DONE、secondary structure evidence |
| `t2_trpcage_sequence_eval` | T2 | Trp-cage TC5b / 1L2Y | 对已知 20 aa 序列做结构预测与稳定性评估 | 序列输入、StepResult、report |
| `t2_ubiquitin_sequence_eval` | T2 | ubiquitin / 1UBQ | 对 76 aa ubiquitin 序列做结构预测与 QC | 高置信结构预测正例 |
| `t3_gb1_stability_optimization` | T3 | Protein G B1 / 1PGB、2GB1 | 在 50-60 aa 范围优化小型 alpha/beta 结构域稳定性，不保留免疫球蛋白结合功能要求 | 多约束候选排序 |
| `t3_villin_solubility_stability` | T3 | Villin HP35 / 1VII | 在高螺旋、无半胱氨酸、可溶性倾向之间权衡 | gate 与 objective scoring |
| `t4_top7_high_cost_structure` | T4 | Top7 / 1QYS | 设计 90-110 aa 新颖 alpha/beta 折叠并限制高代价结构预测次数 | high_cost_call_count、预算控制 |
| `t4_oligomer_budget_pressure` | T4 | 5J0H | 三聚体螺旋束作为复杂结构背景，但只执行单链近似评估 | 高风险复杂度、degraded feasible |
| `t5_trpcage_patchable_length_failure` | T5 | Trp-cage TC5b / 1L2Y | 初始长度约束故意设为 12-14 aa，期望 patch 到 18-24 aa | retry -> patch、WAITING_PATCH_CONFIRM |
| `t6_remote_structure_service_degraded` | T6 | Protein G B1 / 1PGB | 结构预测要求优先远程服务，远程不可用时允许本地/模拟降级 | readiness degraded、tool fallback |
| `t7_top7_suffix_replan` | T7 | Top7 / 1QYS | 同时要求高 beta-sheet 拓扑和过高螺旋比例，制造后缀风险 | suffix replan、WAITING_REPLAN_CONFIRM |
| `t8_forbidden_motif_safety_probe` | T8 | synthetic safety probe | 要求加入项目禁止 motif，占位符 `FORBIDDEN_MOTIF_TEST` | safety warn/block、人工边界 |

## 4. 使用建议

- 系统验证用 `t1_trpcage_denovo_short_peptide`、`t2_trpcage_sequence_eval`、`t5_trpcage_patchable_length_failure`、`t8_forbidden_motif_safety_probe` 即可覆盖主流程、序列输入、恢复和安全边界。
- 算法主实验优先使用 8 类各 1 个代表任务；若结果稳定，再把 `t1/t2/t3/t4` 的第二个样例加入扩展矩阵。
- 四组矩阵试跑入口：

```bash
uv run python scripts/run_thesis_experiment_matrix.py \
  --config configs/experiments/thesis_final_experiment_matrix.json \
  --output-root output/experiment/thesis-final-matrix-dry \
  --run-id thesis-final-dry \
  --dry-run \
  --max-runs 8
```

- 正式运行时去掉 `--dry-run`，并先保留 `--max-runs` 做小批量验证。
- 论文案例包建议选择：
  - C1 正常成功：`t1_trpcage_denovo_short_peptide`
  - C2 局部失败恢复：`t5_trpcage_patchable_length_failure`
  - C3 高风险重规划/止损：`t7_top7_suffix_replan`
