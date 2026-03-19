# 中期论文准备：资料清单与用途索引

- 生成时间：`2026-03-20`
- 目的：为 `../thesis-paper/resources/` 提供一份可直接照搬的参考资料索引。

## 1. 最值得复制的设计文档

### 1.1 系统与方法核心

- `../thesis-project.design/docs/design/architecture.md`
  - 用途：系统总体架构、分层结构、角色关系。
- `../thesis-project.design/docs/design/agent-design.md`
  - 用途：四类 Agent 职责边界与数据契约。
- `../thesis-project.design/docs/design/de-novo-workflow.md`
  - 用途：六阶段方法设计与阶段间循环关系。
- `../thesis-project.design/docs/design/system-implementation-design.md`
  - 用途：实现章节、技术栈、目录结构、落地方式。
- `../thesis-project.design/docs/design/tools-catalog.md`
  - 用途：工具生态与适配器说明。

### 1.2 实验与训练思路

- `../thesis-project.design/docs/experiment/w11-w12-midterm-experiment-plan.md`
  - 用途：研究问题、实验分组、指标体系、图表规划。
- `../thesis-project.design/docs/algorithm-and-llm/llm-read.md`
  - 用途：Planner 专用模型训练与双路回退动机。
- `../thesis-project.design/docs/algorithm-and-llm/train-llm.md`
  - 用途：训练路线、门槛、数据工程与上线策略。
- `../thesis-project.design/docs/algorithm-and-llm/core-algorithm-define.md`
  - 用途：方法定义背景。
- `../thesis-project.design/docs/algorithm-and-llm/algorithm-read.md`
  - 用途：方法相关文献与方案梳理。

## 2. 最值得复制的仓库文档

### 2.1 项目入口与演示

- `README.md`
  - 用途：项目简介与快速运行入口。
- `examples/README_DEMO.md`
  - 用途：演示脚本与答辩展示路径。
- `reports/showcase/full_flow_showcase_guide.md`
  - 用途：答辩或中期展示时的讲解顺序。

### 2.2 方法契约与阶段说明

- `docs/algorithm-and-llm/candidate-set-output-v1.md`
  - 用途：Planner 候选输出字段说明。
- `docs/algorithm-and-llm/s1-sequence-exploration-contract.md`
  - 用途：S1 章节写作。
- `docs/algorithm-and-llm/s3-quality-gate-contract.md`
  - 用途：S3 章节写作。
- `docs/algorithm-and-llm/s4-structure-refinement-contract.md`
  - 用途：S4 章节写作。
- `docs/algorithm-and-llm/requirement2-similarity-secondary-structure-tools.md`
  - 用途：Requirement-2 工具扩展章节。

### 2.3 服务与工具说明

- `services/plm_rest_server/README.md`
  - 用途：远端模型服务接入说明。
- `services/openfold3_rest_server/README.md`
  - 用途：远端结构服务接入说明。

## 3. 最值得复制的验证与总结报告

### 3.1 可直接支撑论文“系统已实现”的

- `reports/full_flow_validation_report.md`
- `reports/usability_validation_report.md`
- `reports/llm_provider_validation_report.md`
- `reports/terminology-unified-2026-03-16.md`

### 3.2 可支撑论文“项目阶段进度与风险”的

- `reports/in-progress-issue-recheck-2026-03-16.md`
- `reports/failure-reason.md`
- `reports/w12-issue-152/release_candidate_draft.md`
- `reports/w12-issue-152/next_stage_backlog.md`

### 3.3 可支撑答辩展示与工程治理的

- `reports/showcase/full_flow_showcase_manifest.json`
- `reports/showcase/full_flow_showcase_guide.md`
- `reports/issue-audit/issue-144.json`
- `reports/issue-audit/issue-149.json`
- `reports/issue-audit/issue-150.json`
- `reports/issue-audit/issue-151.json`
- `reports/issue-audit/issue-159.json`
- `reports/issue-audit/issue-160.json`
- `reports/issue-audit/issue-173.json`

## 4. 关于实验材料的复制策略

### 4.1 建议复制

- 实验设计文档。
- 指标口径文档。
- 方法与公平性约束文档。
- 不依赖具体数值的实验写作草稿。

### 4.2 不建议作为中期论文主参考复制

- 大量 `output/experiment/...` 下的原始结果数据。
- 当前仍可能变动的数值型中间表。
- 会把“阶段性结果”误写成“最终结论”的临时结果文件。

## 5. 两类实验建议只保留无数据版材料

针对中期论文里的两个实验设计，建议只复制以下无数据版材料：

- `../thesis-project.design/docs/experiment/w11-w12-midterm-experiment-plan.md`
- `scripts/w12-issue-171-vertical-a0-a6-experiment.md`
- 本次新增：`reports/thesis-paper-prep/midterm_experiment_designs_2026-03-20.md`

并避免把以下“含当前数值结果”的文档作为主参考放入实验设计目录：

- `reports/w12-issue-174/midterm_experiment_chapter.md`
- `reports/w12-issue-152/three_week_report.md`

这两份可以保留在补充材料区，但不建议作为“实验设计”主稿来源。

## 6. 推荐复制后的目录结构

建议在 `../thesis-paper/resources/` 下组织为：

- `design/`
- `repo-docs/`
- `validation-reports/`
- `issue-progress/`
- `experiment-designs/`
- `generated/`

## 7. 论文章节与资料映射建议

- 绪论/问题定义：
  - `llm-read.md`
  - `algorithm-read.md`
- 系统设计：
  - `architecture.md`
  - `agent-design.md`
  - `de-novo-workflow.md`
- 系统实现：
  - `system-implementation-design.md`
  - `tools-catalog.md`
  - 服务 README
- 实验设计：
  - `w11-w12-midterm-experiment-plan.md`
  - `midterm_experiment_designs_2026-03-20.md`
- 工程验证与讨论：
  - `full_flow_validation_report.md`
  - `usability_validation_report.md`
  - `llm_provider_validation_report.md`
- 项目进展与限制：
  - `project_overview_and_progress_2026-03-20.md`
  - `in-progress-issue-recheck-2026-03-16.md`
  - `next_stage_backlog.md`
