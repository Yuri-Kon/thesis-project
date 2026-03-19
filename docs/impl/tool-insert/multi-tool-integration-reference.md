# 多工具接入归纳（面向 Issue #172 与 Requirement-2）

更新时间：2026-03-16

## 1. 归纳范围与依据

本清单用于后续“多工具接入 + 横向对比实验”实施参考，基于以下来源汇总：

- 设计文档：`../thesis-project.design/docs/design/tools-catalog.md`
- 设计排程：`../thesis-project.design/plan/w12-issues-169-170-experiment-timeline-data-freeze-implementation-plan.md`
- 项目现状：`thesis-project.dev/src/`、`configs/`、`scripts/`、`tests/`

对齐原则：

- 优先按 `tools-catalog` 的 `P0 -> P1 -> P2` 推进。
- 横向对比（E0/E1/E2）必须共享同一 `freeze_id`、统一预算、统一工具白名单。
- 每个工具接入都必须同时落地：ToolKG 描述 + Adapter + 失败码映射 + 测试 + 运行文档。

## 2. 当前项目已接入（可执行）

| 名称 | 网址 | 接入位置（项目） | 接入方式 | 具体功能 | 补充建议 |
| --- | --- | --- | --- | --- | --- |
| ProtGPT2 | https://huggingface.co/nferruz/ProtGPT2 | `src/adapters/protgpt2_adapter.py`、`configs/model_providers.json`、`src/kg/protein_tool_kg.json` | `remote_model_service`（`plm_rest`）/ python | S1 初始序列生成（goal -> sequence + candidates） | 增加远端服务 SLA 与超时分层告警；补齐候选质量统计（长度、低复杂度、非法字符率） |
| NIM ESMFold | https://build.nvidia.com/explore/discover | `src/adapters/nim_adapter.py`、`src/engines/nim_client.py`、`configs/model_providers.json`、`src/kg/protein_tool_kg.json` | `remote_model_service`（`nvidia_nim`） | S2 远程结构预测（sequence -> pdb/plddt） | 补充配额监控与自动降级阈值（NIM -> 本地 ESMFold） |
| ESMFold（本地） | https://github.com/facebookresearch/esm | `src/adapters/esmfold_adapter.py`、`src/engines/nextflow_adapter.py`、`nf/modules/esmfold.nf`、`src/kg/protein_tool_kg.json` | `nextflow` / python | S2 本地结构预测基线路径 | 补充 GPU 资源探针与任务排队指标，避免批量实验抖动 |
| ProteinMPNN | https://github.com/dauparas/ProteinMPNN | `src/adapters/protein_mpnn_adapter.py`、`configs/model_providers.json`、`src/kg/protein_tool_kg.json` | `remote_model_service` / python / nextflow | S4 结构条件序列精修（structure -> sequence） | 增加输入骨架合法性预检与失败码细分（空骨架/格式异常/长度越界） |
| Visualization Toolchain（BioPython + Plotly） | https://biopython.org/ ; https://plotly.com/ | `src/tools/visualization/pipeline.py`、`src/tools/visualization/adapter.py` | python（内嵌可视化流水线） | 结构指标提取、HTML 报告和图表输出 | 目前是汇报链路工具，建议在 ToolKG 中补充为 Summarizer 能力项，统一追踪产物元数据 |

## 3. 近期应接入（P0 缺口）

以下项来自 `tools-catalog.md` 与项目现状差异，按“先补齐六阶段闭环，再做增强”排序。

| 名称 | 网址 | 建议接入位置（项目） | 接入方式 | 具体功能 | 需要补充 |
| --- | --- | --- | --- | --- | --- |
| AlphaFold2 | https://github.com/google-deepmind/alphafold | `src/adapters/alphafold_adapter.py`（新增）、`nf/modules/alphafold.nf`（新增或复用）、`src/kg/protein_tool_kg.json`（已含 tool_id） | nextflow / python | 高精度结构预测，作为 ESMFold 互补与回退路径 | 明确 MSA 依赖准备流程与缓存策略；补齐集成测试 |
| OpenFold | https://github.com/aqlaboratory/openfold | `src/adapters/openfold_adapter.py`（新增）、`src/kg/protein_tool_kg.json`（补充）、`configs/model_providers.json`（如走远端） | python / nextflow | 开源结构预测备选，降低单一路径风险 | 明确与 AlphaFold 的输入/输出兼容层与指标对齐 |
| BioPython QC（独立化） | https://biopython.org/ | `src/adapters/biopython_qc_adapter.py`（新增）、`src/kg/protein_tool_kg.json`（补充 execution） | python | S3 质量门禁（序列/结构基础 QC） | 将当前 visualization 内的 QC 逻辑下沉为可复用 Executor 工具 |
| MMseqs2 | https://github.com/soedinglab/MMseqs2 | `src/adapters/mmseqs2_adapter.py`（新增）、`nf/modules/mmseqs2.nf`（新增）、KG 扩展草案落地 | nextflow / external / python | 序列相似性检索，支持 S3/S5 可解释评价 | 补充数据库版本锁定与重现实验脚本 |
| BLASTP | https://www.ncbi.nlm.nih.gov/books/NBK279690/ | `src/adapters/blastp_adapter.py`（新增）、`nf/modules/blastp.nf`（新增） | nextflow / external / python | 经典相似性基线，与 MMseqs2 做互证 | 统一 hits schema，方便横向聚合分析 |
| DSSP | https://github.com/PDB-REDO/dssp | `src/adapters/dssp_adapter.py`（新增）、`nf/modules/dssp.nf`（新增） | python / external / nextflow | 二级结构注释与质量评估补充 | 增加输出标准化（Q3/Q8）与质量门禁阈值配置 |
| Objective Ranker（执行层化） | 内部实现（无外链） | `src/adapters/objective_ranker_adapter.py`（新增）或 `src/agents/planner.py` 中抽离为可执行模块 | python | S5 多目标打分与 Top-K 汇总 | 明确评分版本号与可回放配置快照，避免口径漂移 |

## 4. 横向对比平台/工具（E0/E1/E2）

以下用于 Issue #172 的“方法学横向对比”数据沉淀，不替代本项目主执行链路。

| 名称 | 网址 | 建议接入位置（项目） | 接入方式 | 具体功能 | 需要补充 |
| --- | --- | --- | --- | --- | --- |
| Inspect AI | https://inspect.aisi.org.uk/ | `scripts/benchmarks/inspect_issue172.py`（建议新增）、`output/experiment/w12-expr-3/issue172-horizontal/inspect/` | Python SDK/CLI | 支持 agent/tool loop 评测与日志追踪，适合 ReAct/ToT/Reflexion 横向实验 | 固化 `dataset + budget + whitelist` 参数模板，保证公平对比 |
| LangSmith | https://docs.langchain.com/langsmith/compare-experiment-results | `scripts/benchmarks/langsmith_issue172.py`（建议新增） | API/SDK | 实验对比、回归定位、trace 追踪 | 仅作为“观测层”，避免侵入主执行逻辑 |
| MLflow GenAI Evaluation | https://mlflow.org/docs/latest/genai/eval-monitor/running-evaluation/prompts/ | `scripts/benchmarks/mlflow_issue172.py`（建议新增） | Python SDK | 运行版本化、指标/产物统一记录、可重复评估 | 与现有 `output/experiment` 目录结构做字段映射 |
| Promptfoo | https://www.promptfoo.dev/docs/intro/ | `scripts/benchmarks/promptfoo/`（建议新增） | CLI + YAML | 快速回归与阈值断言，适合 CI 兜底检查 | 用作轻量回归，不作为唯一结论来源 |
| OpenAI Evals（可选） | https://github.com/openai/evals | `scripts/benchmarks/openai_evals/`（建议新增） | Python/CLI | 标准化 eval harness，可接入模型和工具调用协议 | 适合作为补充评测层；优先级低于 Inspect/LangSmith |

## 5. 建议新增的“接入记录字段”（文档与配置）

为避免后续工具数量增长导致不可维护，建议在 ToolKG 与实验配置中统一追加以下字段：

- `owner`：工具维护责任人。
- `maturity`：`experimental / beta / stable`。
- `cost_model`：调用成本口径（按 token / 按任务 / 按时长）。
- `quota_limit`：配额与速率上限。
- `artifact_schema_version`：输出产物 schema 版本。
- `reproducibility_inputs`：运行重现所需最小输入（镜像、数据库版本、seed）。
- `fallback_chain`：显式主备切换链路（如 `nim_esmfold -> esmfold -> alphafold`）。
- `security_notes`：凭证、数据合规与网络边界要求。

## 6. 最小落地清单（每接入一个新工具都执行）

- 新增/更新 ToolKG 条目（capability/io/constraints/execution/official_link）。
- 新增 Adapter（`src/adapters/`）并注册（`src/adapters/builtins.py` 或运行时装配路径）。
- 增加失败码映射与恢复策略校验（retry -> patch -> replan）。
- 增加单元 + 集成测试（含至少 1 条失败回退路径）。
- 更新运行文档（命令、环境变量、产物位置、门禁阈值）。
- 在横向实验中登记：`freeze_id`、预算、工具白名单、数据版本。

## 7. 备注

- 本文是“接入参考清单”，不改变现有 FSM、角色边界或执行语义。
- 横向对比建议采用“一个主平台 + 一个轻量回归工具”策略，避免一次性引入过多变量。
