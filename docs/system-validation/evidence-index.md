# 系统验证证据索引

更新时间：2026-05-10

本文档为论文“系统测试与验证”章节提供证据编号索引。编号仅用于论文、测试用例表和图表引用，不改变原始文件名。若后续 84-run 矩阵继续产生新日志，应在本文末尾追加，不覆盖已编号证据。

## 1. 证据编号规则

| 前缀 | 含义 | 主要用途 |
|---|---|---|
| FIG-SV | 前端截图 | 论文图、系统验证截图编号 |
| EVD-API | API 响应 | 健康检查、能力就绪、任务/报告接口证据 |
| EVD-TEST | pytest 执行日志 | 自动化测试通过证据 |
| EVD-CLI | CLI 输出 | 命令行入口可用性与限制说明 |
| EVD-EXP | 实验矩阵与运行聚合 | 端到端流程、工具链和算法对照结果 |
| EVD-LOG | EventLog / Snapshot / Report 原始产物 | 状态迁移、恢复、审计链和报告证据 |

## 2. 前端截图证据

| 编号 | 文件 | 页面/场景 | 说明 | 可支撑用例 |
|---|---|---|---|---|
| FIG-SV-01 | `docs/system-validation/06-ui-screenshots/dashboard.png` | Dashboard | 英文界面历史截图，保留作早期验证证据 | TC-S07 |
| FIG-SV-02 | `docs/system-validation/06-ui-screenshots/dashboard-ch.png` | Dashboard | 中文化后的工作区概览 | TC-S07 |
| FIG-SV-03 | `docs/system-validation/06-ui-screenshots/tasker-builder.png` | Task Builder | 任务录入页初版截图 | TC-S07 |
| FIG-SV-04 | `docs/system-validation/06-ui-screenshots/taskbuilder-2.png` | Task Builder | 任务录入表单与字段组展示 | TC-S07 |
| FIG-SV-05 | `docs/system-validation/06-ui-screenshots/taskerbuilder-3.png` | Task Builder | 草稿字段与澄清区域展示 | TC-S07 |
| FIG-SV-06 | `docs/system-validation/06-ui-screenshots/taskerbuilder-4.png` | Task Builder | 任务构建补充状态截图 | TC-S07 |
| FIG-SV-07 | `docs/system-validation/06-ui-screenshots/taskbuilder-ch1.png` | Task Builder | 中文化后的任务构建入口 | TC-S07 |
| FIG-SV-08 | `docs/system-validation/06-ui-screenshots/taskerbuilder-ch2.png` | Task Builder | 中文化字段组展示 | TC-S07 |
| FIG-SV-09 | `docs/system-validation/06-ui-screenshots/taskerbuilder-ch3.png` | Task Builder | 中文化草稿复核区域 | TC-S07 |
| FIG-SV-10 | `docs/system-validation/06-ui-screenshots/taskerbuilder-ch4.png` | Task Builder | 中文化安全预检查/澄清区域 | TC-S07、TC-S10 |
| FIG-SV-11 | `docs/system-validation/06-ui-screenshots/taskerbuilder-ch5.png` | Task Builder | 中文化任务创建补充截图 | TC-S07 |
| FIG-SV-12 | `docs/system-validation/06-ui-screenshots/taskdetail.png` | Task Detail | 任务详情初版截图 | TC-S07、TC-S09 |
| FIG-SV-13 | `docs/system-validation/06-ui-screenshots/task-detail-ch1.png` | Task Detail | 中文化任务详情首页 | TC-S07、TC-S09 |
| FIG-SV-14 | `docs/system-validation/06-ui-screenshots/task-detail-ch2.png` | Task Detail | 中文化任务快照/运行上下文 | TC-S04、TC-S07 |
| FIG-SV-15 | `docs/system-validation/06-ui-screenshots/task-detail-ch3.png` | Task Detail | 中文化候选/决策区域 | TC-S04、TC-S07 |
| FIG-SV-16 | `docs/system-validation/06-ui-screenshots/task-detail-ch4.png` | Task Detail | 中文化报告/结构区域 | TC-S07、TC-S09 |
| FIG-SV-17 | `docs/system-validation/06-ui-screenshots/task-detail-ch5.png` | Task Detail | 中文化结构查看与证据面板补充截图 | TC-S07、TC-S09 |

说明：当前截图集中缺少单独 Timeline 页面截图。Timeline 的 API 与 smoke 已由 EVD-TEST-01 覆盖；若论文需要完整 UI 图，应后续补 `FIG-SV-18 Timeline`。

## 3. API 响应证据

| 编号 | 文件 | 响应摘要 | 可支撑用例 |
|---|---|---|---|
| EVD-API-01 | `docs/system-validation/05-api-results/health.json` | `/health` 返回 `status=ok`，`task_count=0`，包含 KG tool、capability readiness 和路径摘要 | TC-S01、TC-S02 |
| EVD-API-02 | `docs/system-validation/05-api-results/readiness.json` | `/capabilities/readiness` 返回 15 条能力就绪记录：7 ready、1 degraded、7 unavailable；降级/不可用项包含恢复建议 | TC-S01、TC-S11 |

待补建议：将典型 `/task-intakes/schema`、`/tasks/{id}`、`/pending-actions/{id}`、`/tasks/{id}/events`、`/tasks/{id}/report` 响应补入 `docs/system-validation/05-api-results/`，用于替代“仅由 pytest 证明”的接口证据。

## 4. pytest 自动化测试证据

| 编号 | 文件 | 命令范围 | 结果 | 覆盖重点 |
|---|---|---|---|---|
| EVD-TEST-01 | `docs/system-validation/07-test-runs/pytest-api-web.log` | `tests/api/test_api_endpoints.py tests/api/test_web_smoke.py` | 71 passed, 3 warnings | API 合约、Web 页面 bootstrap、task detail、event timeline、task builder |
| EVD-TEST-02 | `docs/system-validation/07-test-runs/pytest-fsm-hitl-snapshot.log` | status、decision、snapshot、event log、snapshot recovery | 107 passed, 1 warning | FSM 状态迁移、HITL 决策、终态不可变、快照恢复、EventLog |
| EVD-TEST-03 | `docs/system-validation/07-test-runs/pytest-safety-recovery-tools.log` | safety、step runner、candidate validation、layered patch、S6 control E2E | 43 passed, 1 warning | 安全 warn/block、工具调用阻断、候选 I/O 边界、retry/patch/replan |
| EVD-TEST-04 | `docs/system-validation/07-test-runs/pytest-cli.log` | `tests/unit/test_cli.py` | 16 passed, 1 warning | CLI 参数、输出、任务查看相关合约 |

## 5. CLI 输出证据

| 编号 | 文件 | 内容 | 结论 |
|---|---|---|---|
| EVD-CLI-01 | `docs/system-validation/07-test-runs/cli-intake-schema.log` | `intake schema --json` 输出，3953 行 | CLI 可返回完整 task-intake 字段注册表 |
| EVD-CLI-02 | `docs/system-validation/07-test-runs/cli-task-show.log` | `task show` 输出，含 task 状态、能力 readiness 与恢复建议 | CLI 可查看任务与能力摘要 |
| EVD-CLI-03 | `docs/system-validation/07-test-runs/cli-timeline.log` | timeline 子命令 usage 输出 | 当前 CLI timeline 子命令未实现，应作为限制说明 |
| EVD-CLI-04 | `docs/system-validation/07-test-runs/cli-report.log` | report 子命令 usage 输出 | 当前 CLI report 子命令未实现，应作为限制说明 |

## 6. 实验矩阵与端到端运行证据

| 编号 | 路径 | 内容 | 状态 | 可支撑用例 |
|---|---|---|---|---|
| EVD-EXP-01 | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t9-clean-001/` | 4 任务 × 4 组策略，共 16 runs；含 `validation_summary.json`、`matrix_report.md`、`run_level_results.jsonl`、`run_log_index.csv`、`run_traceability_index.csv` | 可作为已完成 smoke/clean 证据 | TC-S09、TC-S11 |
| EVD-EXP-02 | `output/experiment/thesis-final-matrix-smoke/thesis-final-smoke-fourgroup-t8-provider-max-001/` | provider max 场景四组 smoke；含矩阵聚合与证据索引 | 可作为工具链与 provider 对照补充证据 | TC-S09、TC-S11 |
| EVD-EXP-03 | `output/experiment/thesis-final-matrix/thesis-final-v1-dry/` | 84-run 最终矩阵 dry manifest；`runs_manifest.json` 中记录 12 task_keys、4 组、84 runs 设计 | 设计冻结证据，不代表实际运行完成 | 84-run 实验设计 |
| EVD-EXP-04 | `data/logs/thesis-final-v1-001_*.jsonl`、`data/snapshots/thesis-final-v1-001_*.jsonl`、`output/reports/thesis-final-v1-001_*.json` | 当前 84-run 正式矩阵的持续产物；本次盘点时已有部分 `thesis-final-v1-001` 日志、快照和报告 | 进行中，不能写作最终统计结论 | 84-run 运行监控 |

说明：EVD-EXP-04 会随正在运行的矩阵增长。论文最终实验章应以完整 84-run 聚合后的 `run_level_results.jsonl`、`matrix_metrics_summary.csv/json`、`matrix_report.md` 为准。

## 7. EventLog、Snapshot 与报告原始证据

| 编号 | 路径 | 内容 | 可支撑用例 |
|---|---|---|---|
| EVD-LOG-01 | `data/logs/int_deterministic_retry_patch_to_done.jsonl`、`data/snapshots/int_deterministic_retry_patch_to_done.jsonl` | 确定性 retry exhausted 后 patch 到 DONE 的事件链与快照 | TC-S12 |
| EVD-LOG-02 | `data/logs/int_layered_patch_*.jsonl`、`data/snapshots/int_layered_patch_*.jsonl` | 分层 patch、远程到本地 fallback、高风险 patch 等恢复场景 | TC-S12 |
| EVD-LOG-03 | `data/logs/int_s6_*.jsonl`、`data/snapshots/int_s6_*.jsonl` | S6 控制层 E2E、patch decision replay、matrix S3 replan、terminal stop 审计链 | TC-S12、TC-S13 |
| EVD-LOG-04 | `data/logs/task_auto_plan.jsonl`、`data/logs/task_auto_patch_repeat.jsonl`、`data/logs/task_auto_replan*.jsonl` | 自动计划、自动 patch、自动 replan 事件链 | TC-S03、TC-S12、TC-S13 |
| EVD-LOG-05 | `output/reports/thesis-final-smoke-fourgroup-t9-clean-001_*.json` | t9 clean run 的报告 JSON | TC-S09、TC-S11 |
| EVD-LOG-06 | `output/reports/task_*.json` | 历史任务报告 JSON 集合 | TC-S09 |

## 8. 测试用例到证据编号映射

| 用例 | 主证据编号 | 辅助证据编号 |
|---|---|---|
| TC-S01 | EVD-API-01、EVD-API-02 | EVD-TEST-01 |
| TC-S02 | EVD-TEST-01 | EVD-API-01、EVD-API-02 |
| TC-S03 | EVD-TEST-02、EVD-LOG-04 | EVD-EXP-01 |
| TC-S04 | EVD-TEST-02 | FIG-SV-15 |
| TC-S05 | EVD-TEST-02 | EVD-LOG-03 |
| TC-S06 | EVD-TEST-02 | EVD-LOG-01、EVD-LOG-02、EVD-LOG-03 |
| TC-S07 | FIG-SV-01 至 FIG-SV-17、EVD-TEST-01 | EVD-API-01 |
| TC-S08 | EVD-TEST-04、EVD-CLI-01、EVD-CLI-02 | EVD-CLI-03、EVD-CLI-04 |
| TC-S09 | EVD-EXP-01、EVD-LOG-05 | FIG-SV-16、FIG-SV-17 |
| TC-S10 | EVD-TEST-03 | FIG-SV-10 |
| TC-S11 | EVD-TEST-03、EVD-EXP-01 | EVD-API-02 |
| TC-S12 | EVD-TEST-03、EVD-LOG-01、EVD-LOG-02 | EVD-LOG-03 |
| TC-S13 | EVD-TEST-02、EVD-TEST-03、EVD-LOG-03 | EVD-LOG-04 |

## 9. 当前缺口

| 缺口 | 影响 | 建议补充 |
|---|---|---|
| 缺少单独 Timeline 页面截图 | UI 证据链中 timeline 页面只能由 smoke 和 API 支撑 | 补 `FIG-SV-18 Timeline` |
| API 典型任务响应未全部归档 | TC-S02/TC-S03 目前主要依赖 pytest 日志和源码测试 | 补 task-intake、task、pending action、events、report JSON |
| Snapshot/Plan diff 未复制到 `docs/system-validation/04-data-consistency/` | 论文引用路径较分散 | 可以保留原路径，但建议建立 `04-data-consistency/README.md` 或复制关键样本 |
| 84-run 正式矩阵仍在进行中 | 不能写最终实验结论 | 等完整聚合产物生成后追加 `EVD-EXP-05` |
