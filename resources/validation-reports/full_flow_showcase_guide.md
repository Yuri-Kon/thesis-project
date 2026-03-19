# 全流程展示操作手册

## 1. 一次性准备

- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/run_demo.py --port 8000 --exit-after-smoke`
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/run_w12_issue151_demo_audit.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/generate_w12_issue174_midterm_pack.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/generate_w12_issue152_release_pack.py`

## 2. 启动长期运行界面

- API 演示服务：`UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/run_demo.py --port 8000 --no-smoke-test`
- HITL 候选对比服务：`UV_CACHE_DIR=/tmp/uv-cache uv run python examples/run_hitl_candidate_ui_demo.py --serve --port 8012`

## 3. 现场展示顺序

1. 打开 `http://127.0.0.1:8000/docs` 和 `http://127.0.0.1:8000/health`，先展示服务可用性。
2. 打开 `http://127.0.0.1:8012/ui/tasks/task_demo_142`，展示候选对比、排序、风险/成本和人工决策界面。
3. 打开 `http://127.0.0.1:8012/ui/tasks/task_demo_142/events`，展示种子 HITL 任务的事件时间线。
4. 打开 `output/demo/w12-issue-151/replay-record-001-six-stage-hitl.md`，讲解端到端回放。
5. 打开 `output/demo/w12-issue-151/replay-record-002-tool-fallback.md`，讲解 patch/recovery 与工具切换。
6. 打开 `reports/w12-issue-174/midterm_experiment_chapter.md` 和 `reports/w12-issue-152/three_week_report.md`，用实验与报告证据收尾。

## 4. 关键设计点检查清单

### 1. FSM 与 HITL 暂停/恢复

- 展示入口：`http://127.0.0.1:8012/ui/tasks/task_demo_142`
- 检查点：必须能看到候选对比、默认推荐、人工决策提交，以及决策后状态继续推进。
- 证据：
  - `output/demo/w12-issue-151/replay-record-001-six-stage-hitl.md` [已就绪] - WAITING_ENTER -> DECISION_APPLIED -> WAITING_EXIT 回放记录
  - `output/demo/w12-issue-151/release-validation.md` [已就绪] - Issue #151 审计门禁摘要

### 2. 分层恢复与工具回退

- 展示入口：`output/demo/w12-issue-151/replay-record-002-tool-fallback.md`
- 检查点：要展示 REPLACE_TOOL 或路由决策字段，并解释为什么回退不破坏系统契约。
- 证据：
  - `output/demo/w12-issue-151/replay-record-002-tool-fallback.md` [已就绪] - from_tool -> to_tool 回放记录
  - `scripts/w12-issue-150-dual-route-fallback.md` [已就绪] - 运行时回退触发条件与审计字段

### 3. 可审计性与可回放

- 展示入口：`http://127.0.0.1:8000/ui/tasks/<task_id>/events`
- 检查点：时间线页面与 markdown 回放记录必须在事件顺序和任务结果上保持一致。
- 证据：
  - `output/demo/w12-issue-151/logs/int_s6_patch_decision_replay_done.jsonl` [已就绪] - 原始可回放事件日志
  - `reports/w12-issue-152/artifact_evidence_index.csv` [已就绪] - 报告追溯用产物索引

### 4. 实验与报告证据

- 展示入口：`reports/w12-issue-174/midterm_experiment_chapter.md`
- 检查点：要明确说明项目已具备演示与报告能力，但因为 #149 门禁仍阻断，所以还不能宣称正式可发布。
- 证据：
  - `reports/w12-issue-174/midterm_experiment_chapter.md` [已就绪] - 中期实验章节草稿
  - `reports/w12-issue-152/three_week_report.md` [已就绪] - 三周成果总报告
  - `reports/w12-issue-152/release_candidate_draft.md` [已就绪] - RC 草案与阻断项摘要

## 5. 讲解备注

- 最优主线是：可用性 -> HITL -> 回放/审计 -> 回退机制 -> 实验/报告证据。
- 不要夸大当前实验结果。准确表述应是：系统已经具备演示能力和证据整理能力，但正式发布仍受离线门禁缺口阻断。
- 如果时间不足，可以只保留第 1、2、4、6 步。
