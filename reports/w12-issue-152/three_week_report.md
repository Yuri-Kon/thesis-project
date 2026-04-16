# W12 三周成果总报告（Issue #152 Interim Pack）

- generated_at: `2026-03-19T09:42:32.511857+00:00`
- candidate_version: `v0.3.0-rc1`
- dataset_version: `w11-sft-dataset-v1.1-20260315-57fc60d-r02`

## 1. 当前完成度

- 已有可直接复用产物：#148 训练、#149 离线评估、#150 双路回退、#151 演示审计、#171 纵向实验、#173 治理复核。
- `#172` 横向 E0/E1/E2 因外部平台依赖延期，因此 `#174` 仅能生成中期版章节草稿，不能按原始 issue 口径完全关闭。
- 当前版本更适合定义为“可演示、中期可引用、但未达正式发布门禁”的候选包。

## 2. 关键实现与证据

- 训练基线：`v0.3.0-rc1`，基座模型 `sshleifer/tiny-gpt2`，QLoRA `yes`。
- 训练复现命令：`scripts/run_w12_issue148_sft_qlora.py --config configs/training/w12_issue148_sft_qlora_p0_p1.json`
- 演示场景：`six_stage_hitl_replay, tool_fallback_remote_to_local`
- 演示审计检查：`{'audit_chain_pendingaction_decision_eventlog': True, 'tool_fallback_switch_recorded': True, 'e2e_flow_reaches_done': True}`
- 治理全局指标：failure_traceable_rate=`1.0`，waiting_chain_complete_rate=`0.0`，replay_success_rate=`0.0`
- 中期章节草稿：`reports/w12-issue-174/midterm_experiment_chapter.md`

## 3. 统一结论与限制

- RC Gate-B 发布阻断：`yes`
- 阻断指标：`patch_minimality_hit_rate, suffix_replan_prefix_preservation_rate`
- 当前纵向实验说明实验管线可复现，但尚未形成正向任务成功率结果，论文中应按“已完成工程闭环、效果仍待加强”来表述。
- 治理方面，失败可追溯性已经具备，但 WAITING/Decision 主实验样本不足，需继续补充可回放样本。

## 4. 下一阶段建议

- 优先恢复 #172 所需外部平台条件，再补齐 E0/E1/E2 横向对照。
- 基于 #172 结果刷新 #174 正式版章节与图表，避免中期稿长期停留为占位。
- 继续采集能触发 patch/suffix_replan 的真实样本，修复 #149 里两个门禁指标的空值问题。
- 若只面向中期答辩，建议以 #151 演示链 + #171/#173 结果表 + #149 阻断项说明构成展示主线。

## 5. RC 草案结论

- 版本号建议保持 `v0.3.0-rc1`，但仅作为候选演示版，不进入正式版本发布流程。
- 兼容性说明：当前交付不引入新 FSM 状态，不改变 HITL 决策所有权；回退策略通过配置开关控制。
- 已知问题：离线门禁仍被空值指标阻断；横向对照延期；主实验 WAITING 链样本不足。
- 回退策略：`runtime_fallback.force_external_only=False`，环境变量 `PLANNER_FORCE_EXTERNAL_FALLBACK` 可一键熔断。
