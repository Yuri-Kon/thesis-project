---
doc_key: tools
version: 1.1
status: stable
depends_on: [impl]
---

# Tools Catalog(候选工具清单)

> 本文档用于记录 **当前系统架构下，可接入的真实工具候选集合**
> 工具按照 **Executor / Visualization / Summarizer** 三类划分
> 不涉及任务规划逻辑，仅关注:
>
> - 工具真实存在，在生物信息学领域被广泛应用
> - 与现有系统架构的契合度
> - 为后续逐步接入与替换提供多样选择

> 说明：
> 当前已经投入使用工具的统一成本/风险元数据，不再散落定义；
> 正式归一化配置见：
> `docs/design/active-tool-metadata-profile.md`

______________________________________________________________________

## 1. Executor 可选择的工具(计算 / 评估类)

<!-- SID:tools.executor.overview -->

> Executor 负责执行实际计算任务，通常耗时较长，产出结构化 artifacts.
> 以下工具可通过 ToolAdapter 以 `python / nextflow / external` 方式接入。

当前已进入主规划、主恢复或主实验路径的活跃工具包括：

- `protgpt2`
- `protein_mpnn`
- `esmfold`
- `nim_esmfold`
- `openfold`
- `biopython_qc`
- `dssp`
- `objective_ranker`

______________________________________________________________________

### 1.1 序列生成类(Sequence Generation)

#### ProtGPT2 (PLM, Hugging Face)

<!-- SID:tools.protgpt2.spec -->

- 类型：初始序列生成（de novo / protein LM）
- 输入：
  - `goal`: 设计目标描述（可选）
  - `length_range`: [min, max]
  - `num_candidates`: 生成候选数量
  - `prompt`: 可选提示（模板片段/引导片段）
- 输出：
  - `sequence`: 选定的一条候选序列
  - `candidates`: 候选序列列表（可含 perplexity / score）
  - `artifacts`: 生成的 FASTA / JSON 文件路径
- 执行方式：支持两种路径（按优先级）
  1. **本地 Hugging Face (python)**
     - `transformers` + `torch` 本地推理
     - model_id: `nferruz/ProtGPT2`
  1. **SSH 远程主机 (remote_model_service)**
     - 通过 `SSHModelInvocationService` 提交作业并下载结果
     - 远端部署 Hugging Face 模型与推理脚本
- 运行假设（本地路径）：
  - 可访问 Hugging Face 模型权重（缓存或镜像）
  - 可用 CPU/GPU（GPU 提升吞吐）
- 运行假设（SSH 路径）：
  - SSH key 已配置，可无交互访问远程主机
  - 远端环境包含 `transformers`/`torch` 与 ProtGPT2 权重
- 执行配置（SSH 示例）：
  ```json
  {
    "backend": "remote_model_service",
    "provider": "ssh",
    "model_id": "nferruz/ProtGPT2",
    "sync_mode": false
  }
  ```
- 产物目录约定：`output/sequences/`、`output/artifacts/`
- 非目标：
  - 结构/功能条件精确控制
  - 多序列批处理优化（可由上层批量调度实现）
- 备注：
  - 作为“初始序列生成器”，下游可接 ESMFold / ProteinMPNN
  - 生成候选可先做长度、字符合法性与低复杂度过滤

### 1.2 结构预测类(Structure Prediction)

#### ESMFold

<!-- SID:tools.esmfold.spec -->

- 类型：蛋白质结构预测
- 输入：单条氨基酸序列(FASTA / string)
- 输出：PDB 文件、置信度(pLDDT)
- 执行方式：支持两种路径（按优先级）
  1. **NVIDIA NIM 远程调用**（推荐，Week 5 优先）
     - 通过 `nim_esmfold` 工具调用 NVIDIA NIM Biology API
     - 无需本地 GPU，简化部署
     - 依赖 `NIM_API_KEY` 环境变量
  1. **本地 Nextflow**（备选）
     - 仅通过 Nextflow 调度容器，不提供 docker run/compose 路径
     - 需要本地 GPU
- 运行假设（本地 Nextflow 路径）：
  - Nextflow 已安装，可通过 `nextflow --info` 验证
  - profile: `docker` / `podman`（Fedora 开发环境默认 podman）
  - 容器引擎：Docker 或 Podman
  - GPU 必须存在（系统不负责 GPU 管理）
- 运行假设（NIM 路径）：
  - 网络可用
  - API Key 已配置（`NIM_API_KEY` 环境变量）
- 模块位置：
  - NIM 路径：`src/engines/nim_client.py`、`src/adapters/nim_adapter.py`
  - Nextflow 路径：`nf/modules/esmfold.nf`
- 产物目录约定：`output/pdb/`、`output/metrics/`、`output/artifacts/`（文件名包含 `task_id`）
- 非目标：
  - batch / 多序列
  - GPU 管理
  - 并发/并行
- 备注:
  - 轻量，无需 MSA
  - 适合作为第一个真实结构工具
  - NIM 路径优先用于开发与演示，Nextflow 路径用于本地高性能计算
- 控制流与执行边界：见 `docs/design/system-implementation-design.md` 的"Nextflow 接入边界与控制流约束"

#### NIM ESMFold

<!-- SID:tools.nim_esmfold.spec -->

- 类型：蛋白质结构预测（远程）
- 输入：`{"sequence": str}` 单条氨基酸序列
- 输出：
  - `pdb_path`: PDB 文件路径
  - `plddt`: 置信度分数（float）
  - `pdb_string`: PDB 内容字符串
- 执行方式：`remote_model_service`（通过 NVIDIA NIM API）
- 执行配置：
  ```json
  {
    "backend": "remote_model_service",
    "provider": "nvidia_nim",
    "model_id": "nvidia/esmfold",
    "sync_mode": true
  }
  ```
- 运行约束：
  - 前置条件：`sequence_provided`
  - 资源假设：`network_available`、`nim_api_key_configured`
  - 限制：`max_length: 400`（序列最大长度）
- 成本评分：`0.3`（相对较低，适合快速迭代）
- 安全级别：`1`（无特殊风险）
- 失败码映射（见 `src/workflow/errors.py`）：
  | FailureCode         | FailureType   | 触发场景          | 恢复动作                          |
  | ------------------- | ------------- | ----------------- | --------------------------------- |
  | NIM_AUTH_FAILED     | NON_RETRYABLE | API key 无效/过期 | HITL（凭证问题）                  |
  | NIM_QUOTA_EXCEEDED  | RETRYABLE     | API 配额/速率限制 | 带退避重试，然后 patch 到替代工具 |
  | NIM_MODEL_NOT_FOUND | NON_RETRYABLE | 请求的模型不可用  | Patch 到替代工具                  |
  | NIM_INVALID_INPUT   | NON_RETRYABLE | 输入验证失败      | Patch step 输入                   |
  | NIM_MODEL_ERROR     | RETRYABLE     | 模型内部错误      | 重试，然后 replan                 |
- 模块位置：`src/engines/nim_client.py`、`src/adapters/nim_adapter.py`
- 配置文件：`configs/model_providers.json`
- 备注：
  - 当 `NIM_API_KEY` 存在时自动注册到 adapter registry
  - 与本地 `esmfold` 工具能力兼容，可作为替代选项
  - Planner 可根据 KG 选择 `protein_mpnn → esmfold` 或 `protein_mpnn → nim_esmfold`

#### AlphaFold / OpenFold

<!-- SID:tools.alphafold.spec -->

- 类型: 高精度结构预测
- 输入: 序列 + MSA
- 输出: PDB、pLDDT
- 接入方式: nextflow
- 备注:
  - 成本高
  - 更适合作为后期高质量的验证工具

______________________________________________________________________

### 1.3 序列与结构质量评估

#### BioPython(PDB / Seq 模块)

- 类型: 基础结构 / 序列解析
- 输入: PDB / FASTA
- 输出: 统计指标(长度、缺失残基、组成等)
- 接入方式: python
- 备注:
  - 轻量、稳定
  - 非常适合作为 Executor 中的低成本 QC

#### MMseqs2 / BLAST

- 类型: 序列相似性搜索
- 输入: 序列
- 输出: 相似序列表(TSV)
- 接入方式: nextflow / external
- 备注:
  -用于结果可信度评估
  - 不影响主要流程，可选

______________________________________________________________________

### 1.4 结构与理化性质评估

#### DSSP

- 类型: 二级结构分析
- 输入: PDB
- 输出: 二级结构注释
- 接入方式: python / external
- 备注:
  - 适合作为结构报告的补充信息

______________________________________________________________________

## 2. 可视化工具(Visualization)

> 可视化工具用于 **展示实验结果**\
> 推荐用 **SummarizerAgent** 调用，而不是直接影响 Executor 流程

______________________________________________________________________

### 2.1 三维结构可视化(3D)

#### Mol\*(Molstar)

- 类型: 网页端交互式 3D 结构可视化
- 输入: PDB文件
- 输出: HTML 页面中的交互视图
- 接入方式:
  - SummarizerAgent 生成 HTML 并嵌入 Mol\*
- 优点:
  - 生信领域标准工具
  - 无需自行实现 3D 渲染
  - 非常适合展示

#### NGL Viewer

- 类型: 网页端 3D 结构查看器
- 输入: PDB
- 输出: 交互视图
- 接入方式: HTML 嵌入
- 备注:
  - Mol\* 的可替代方案

#### PyMol

- 类型: 桌面级结构渲染工具
- 输入: PDB
- 输出: PNG / session 文件
- 接入方式:
  - python / subprocess 调用
- 备注:
  - 适合生成论文级静态图片
  - 不提供网页交互

______________________________________________________________________

### 2.2 指标与置信度可视化

#### Matplotlib / Seaborn

- 类型：静态科学绘图
- 输入：数值指标（如 pLDDT）
- 输出：PNG
- 接入方式：python
- 备注：
  - 实现成本低
  - 适合早期阶段

#### Plotly

- 类型：交互式可视化
- 输入：指标数据
- 输出：HTML
- 接入方式：python
- 备注：
  - 适合展示多候选对比
  - 可嵌入 Summarizer 报告

______________________________________________________________________

## 3. Summarizer 可选择的工具（报告与汇总）

> Summarizer 的职责是：
> **将 Executor 的结果转化为“科研人员可理解的实验结果展示”**。

______________________________________________________________________

### 3.1 报告生成

#### Markdown / HTML Report Generator

- 类型：实验报告生成
- 输入：
  - StepResult
  - artifacts（PDB、FASTA、TSV）
  - metrics
- 输出：
  - report.md
  - report.html
- 接入方式：python
- 备注：
  - HTML 报告中可嵌入 Mol\*、Plotly 图表
  - 不影响任务最终状态

#### PDF 导出（可选）

- 工具：wkhtmltopdf / playwright
- 输入：HTML 报告
- 输出：PDF
- 接入方式：external / nextflow
- 备注：
  - 用于提交或归档

______________________________________________________________________

### 3.2 结果对比与聚合

#### Pandas

- 类型：表格与结果聚合
- 输入：多个 StepResult / DesignResult
- 输出：对比表、统计数据
- 接入方式：python
- 备注：
  - 用于多候选结果对比
  - 可直接驱动可视化工具

______________________________________________________________________

## 4. 推荐的接入优先级（现实可行）

<!-- SID:tools.integration.priority -->

本节给出面向当前课题落地顺序的工具接入优先级，用于区分近期必须接入的执行链路、可增强的人机展示层，以及更远期的扩展能力。

### P0（近期最值得接入）

- ProtGPT2（PLM 初始序列生成）
- ESMFold（Executor）
- Mol\*（Summarizer / Visualization）
- Matplotlib 或 Plotly（指标可视化）
- HTML 报告生成（Summarizer）

### P1（中期增强）

- PyMOL（静态渲染）
- MMseqs2 / BLAST（相似性分析）
- DSSP（二级结构）

### P2（远期扩展）

- AlphaFold / OpenFold
- 更复杂的序列 logo / MSA 可视化

______________________________________________________________________

## 5. ToolKG 扩展草案（面向训练数据）

<!-- SID:tools.kg_extension.draft -->

> 目标：为后续模型训练准备高覆盖度、多来源、可追溯的数据生产工具链。
> 本节给出面向人阅读的扩展草案；结构化版本可与 `thesis-project.dev/src/kg/protein_tool_kg/extension_draft_v0.1.json` 对齐维护。

### 5.1 能力层（capability_id）

| capability_id                  | 语义                 | 对应阶段             |
| ------------------------------ | -------------------- | -------------------- |
| sequence_generation            | 初始候选序列生成     | 1 序列探索           |
| structure_prediction           | 序列到结构映射       | 2 结构映射           |
| sequence_design                | 结构条件序列精修     | 4 结构条件精修       |
| quality_qc                     | 序列/结构硬门禁评估  | 3 质量门禁           |
| objective_scoring              | 多目标打分与排序     | 5 目标/功能/物性评估 |
| sequence_similarity_search     | 序列相似性检索       | 3,5                  |
| remote_homology_search         | 远同源/谱系检索      | 5                    |
| structure_similarity_search    | 结构相似性检索       | 5                    |
| secondary_structure_annotation | 二级结构注释         | 3,5                  |
| function_annotation            | 功能域/GO 注释       | 5                    |
| physicochemical_scoring        | 理化与表面特征打分   | 5                    |
| stability_simulation           | 稳定性模拟与轨迹评估 | 5                    |
| docking_scoring                | 结合/对接打分        | 5                    |
| backbone_generation            | 结构骨架生成         | 1,4                  |
| inverse_folding                | 逆折叠序列生成       | 4                    |
| patch_replan_control           | Patch/Replan 控制    | 6 控制层             |

### 5.2 I/O 类型层（io_type）

| io_type_id                              | 输入关键字段                              | 输出关键字段                        |
| --------------------------------------- | ----------------------------------------- | ----------------------------------- |
| goal_to_sequence_candidates             | goal, prompt, length_range                | sequence, candidates                |
| sequence_to_structure                   | sequence                                  | pdb_path, plddt                     |
| structure_to_sequence                   | pdb_path                                  | sequence, sequence_score            |
| sequence_structure_to_qc_metrics        | sequence, pdb_path, plddt                 | qc_flags, qc_metrics, pass_fail     |
| candidates_to_objective_scores_topk     | candidates, qc_metrics, structure_metrics | score_table, top_k                  |
| sequence_to_similarity_hits             | sequence                                  | similarity_hits, identity, coverage |
| sequence_to_homology_profile            | sequence                                  | hmm_profile, homology_hits          |
| structure_to_similarity_hits            | pdb_path                                  | structure_hits, tm_score            |
| structure_to_secondary_structure        | pdb_path                                  | secondary_structure, ss_summary     |
| sequence_or_structure_to_function_terms | sequence/pdb_path                         | domain_terms, go_terms              |
| structure_to_surface_and_energy         | pdb_path                                  | sasa, energy_scores                 |
| trajectory_to_stability_metrics         | md_trajectory, pdb_path                   | rmsd, rg, stability_metrics         |
| structure_ligand_to_binding_score       | pdb_path, ligand                          | binding_score, poses                |
| prompt_to_backbone                      | goal, motif, condition                    | pdb_path, backbone_candidates       |
| structure_to_inverse_folding_candidates | pdb_path                                  | sequence_candidates, sequence       |

### 5.3 工具候选清单（按优先级）

> 字段说明：
>
> - `adapter 接入方式`：可并行维护多后端（python/nextflow/external_api/remote_model_service）。
> - `优先级`：`P0` 先接入，`P1` 增强，`P2` 扩展。

#### P0（必须优先，支撑六阶段闭环 + 训练数据起量）

| tool_id          | capability_id                              | io_type                             | adapter 接入方式                             | 优先级 | 官方链接                                      |
| ---------------- | ------------------------------------------ | ----------------------------------- | -------------------------------------------- | ------ | --------------------------------------------- |
| protgpt2         | sequence_generation                        | goal_to_sequence_candidates         | remote_model_service / external_api / python | P0     | https://huggingface.co/nferruz/ProtGPT2       |
| esmfold          | structure_prediction                       | sequence_to_structure               | nextflow / python                            | P0     | https://github.com/facebookresearch/esm       |
| nim_esmfold      | structure_prediction                       | sequence_to_structure               | remote_model_service / external_api          | P0     | https://build.nvidia.com/explore/discover     |
| protein_mpnn     | sequence_design, inverse_folding           | structure_to_sequence               | remote_model_service / python / nextflow     | P0     | https://github.com/dauparas/ProteinMPNN       |
| alphafold2       | structure_prediction                       | sequence_to_structure               | nextflow / python                            | P0     | https://github.com/google-deepmind/alphafold  |
| openfold         | structure_prediction                       | sequence_to_structure               | python / nextflow                            | P0     | https://github.com/aqlaboratory/openfold      |
| biopython_qc     | quality_qc                                 | sequence_structure_to_qc_metrics    | python                                       | P0     | https://biopython.org/                        |
| mmseqs2          | sequence_similarity_search                 | sequence_to_similarity_hits         | nextflow / external_api / python             | P0     | https://github.com/soedinglab/MMseqs2         |
| blastp           | sequence_similarity_search                 | sequence_to_similarity_hits         | nextflow / external_api / python             | P0     | https://www.ncbi.nlm.nih.gov/books/NBK279690/ |
| dssp             | secondary_structure_annotation, quality_qc | structure_to_secondary_structure    | python / external_api / nextflow             | P0     | https://github.com/PDB-REDO/dssp              |
| objective_ranker | objective_scoring                          | candidates_to_objective_scores_topk | python                                       | P0     | 内部实现（无外部官网）                        |

#### P1（中期增强，提升标签维度与泛化）

| tool_id          | capability_id                                               | io_type                                 | adapter 接入方式                 | 优先级 | 官方链接                                         |
| ---------------- | ----------------------------------------------------------- | --------------------------------------- | -------------------------------- | ------ | ------------------------------------------------ |
| hmmer            | remote_homology_search                                      | sequence_to_homology_profile            | nextflow / python / external_api | P1     | https://hmmer.org/                               |
| hhsuite          | remote_homology_search                                      | sequence_to_homology_profile            | nextflow / python                | P1     | https://github.com/soedinglab/hh-suite           |
| foldseek         | structure_similarity_search                                 | structure_to_similarity_hits            | nextflow / python                | P1     | https://github.com/steineggerlab/foldseek        |
| tmalign          | structure_similarity_search                                 | structure_to_similarity_hits            | external_api / python            | P1     | https://zhanggroup.org/TM-align/                 |
| usalign          | structure_similarity_search                                 | structure_to_similarity_hits            | external_api / python            | P1     | https://zhanggroup.org/US-align/                 |
| interproscan     | function_annotation, objective_scoring                      | sequence_or_structure_to_function_terms | nextflow / python / external_api | P1     | https://github.com/ebi-pf-team/interproscan      |
| freesasa         | physicochemical_scoring, quality_qc                         | structure_to_surface_and_energy         | python / external_api            | P1     | https://github.com/mittinatten/freesasa          |
| rosetta          | physicochemical_scoring, sequence_design, objective_scoring | structure_to_surface_and_energy         | python / nextflow                | P1     | https://www.pyrosetta.org/                       |
| mdanalysis       | stability_simulation, objective_scoring                     | trajectory_to_stability_metrics         | python                           | P1     | https://www.mdanalysis.org/pages/documentation/  |
| rcsb_data_api    | function_annotation, objective_scoring                      | sequence_or_structure_to_function_terms | external_api / python            | P1     | https://data.rcsb.org/index.html                 |
| alphafold_db_api | structure_prediction, objective_scoring                     | sequence_to_structure                   | external_api / python            | P1     | https://www.alphafold.ebi.ac.uk/                 |
| uniprot_api      | function_annotation, objective_scoring                      | sequence_or_structure_to_function_terms | external_api / python            | P1     | https://www.uniprot.org/help/programmatic_access |

#### P2（远期扩展，提升探索上限）

| tool_id       | capability_id                           | io_type                                 | adapter 接入方式                 | 优先级 | 官方链接                                            |
| ------------- | --------------------------------------- | --------------------------------------- | -------------------------------- | ------ | --------------------------------------------------- |
| openmm        | stability_simulation                    | trajectory_to_stability_metrics         | python                           | P2     | https://docs.openmm.org/latest/userguide/index.html |
| gromacs       | stability_simulation                    | trajectory_to_stability_metrics         | nextflow / external_api          | P2     | https://manual.gromacs.org/current/index.html       |
| autodock_vina | docking_scoring, objective_scoring      | structure_ligand_to_binding_score       | nextflow / python / external_api | P2     | https://autodock-vina.readthedocs.io/en/latest/     |
| rfdiffusion   | backbone_generation                     | prompt_to_backbone                      | python / nextflow                | P2     | https://github.com/RosettaCommons/RFdiffusion       |
| esm_if1       | inverse_folding, sequence_design        | structure_to_inverse_folding_candidates | python                           | P2     | https://github.com/facebookresearch/esm             |
| chai1         | structure_prediction, objective_scoring | sequence_to_structure                   | python / external_api            | P2     | https://github.com/chaidiscovery/chai-lab           |
| boltz         | structure_prediction, objective_scoring | sequence_to_structure                   | python / nextflow                | P2     | https://github.com/jwohlwend/boltz                  |

### 5.4 落地备注（与当前系统对齐）

- 与现有运行时 KG 兼容：新增能力与 IO 采用增量方式，不移除既有字段。
- 先执行 P0：优先形成“序列探索 → 结构映射 → 质量门禁 → 结构精修 → 目标打分 → Patch/Replan”可运行闭环。
- 每接入一个工具，必须同步：ToolAdapter + 单测 + 集成测试 + 失败码映射。

______________________________________________________________________

## 6. 设计原则（约束）

<!-- SID:tools.adapter.constraints BEGIN -->

- 所有工具：
  - 不直接与人交互
  - 只通过 ToolAdapter / Summarizer 被调用
- 可视化工具失败：
  - 不影响任务 DONE
  - 仅影响展示结果
- 工具替换：
  - 不应影响系统整体架构
  - 同类工具可并存，供后续选择
- 序列生成类工具：
  - 支持多种执行后端：`python`（本地 Hugging Face）、`remote_model_service`（SSH 远程）
  - 输出至少包含 `sequence` 与 `candidates`，并生成可追溯 artifacts
- 结构预测类工具：
  - 支持多种执行后端：`nextflow`（本地）、`remote_model_service`（远程 API）
  - 同一能力可由多个工具提供（如 `esmfold` 和 `nim_esmfold` 均提供 `structure_prediction`）
  - Planner 通过 ProteinToolKG 选择合适的工具路径
- 远程模型服务（`remote_model_service`）：
  - 通过 Provider 配置系统管理 API 凭证与端点（见 `configs/model_providers.json`）
  - 失败码需映射到统一的 `FailureCode` 体系
  - 支持自动回退到本地工具（如 NIM 不可用时回退到 Nextflow）

<!-- SID:tools.adapter.constraints END -->
