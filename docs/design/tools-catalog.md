---
doc_key: tools
version: 1.0
status: stable
depends_on: [impl]
---

# Tools Catalog(候选工具清单)

> 本文档用于记录 **当前系统架构下，可接入的真实工具候选集合**
> 工具按照 **Executor / Visualization / Summarizer** 三类划分
> 不涉及任务规划逻辑，仅关注:
>
> -  工具真实存在，在生物信息学领域被广泛应用
> - 与现有系统架构的契合度
> - 为后续逐步接入与替换提供多样选择

---

## 1. Executor 可选择的工具(计算 / 评估类)
<!-- SID:tools.executor.overview -->

> Executor 负责执行实际计算任务，通常耗时较长，产出结构化 artifacts.
> 以下工具可通过 ToolAdapter 以 `python / nextflow / external` 方式接入。

---

### 1.1 结构预测类(Structure Prediction)

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
  2. **本地 Nextflow**（备选）
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
  | FailureCode | FailureType | 触发场景 | 恢复动作 |
  |-------------|-------------|----------|----------|
  | NIM_AUTH_FAILED | NON_RETRYABLE | API key 无效/过期 | HITL（凭证问题） |
  | NIM_QUOTA_EXCEEDED | RETRYABLE | API 配额/速率限制 | 带退避重试，然后 patch 到替代工具 |
  | NIM_MODEL_NOT_FOUND | NON_RETRYABLE | 请求的模型不可用 | Patch 到替代工具 |
  | NIM_INVALID_INPUT | NON_RETRYABLE | 输入验证失败 | Patch step 输入 |
  | NIM_MODEL_ERROR | RETRYABLE | 模型内部错误 | 重试，然后 replan |
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

---

### 1.2 序列与结构质量评估

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

---

### 1.3 结构与理化性质评估

#### DSSP

- 类型: 二级结构分析
- 输入: PDB
- 输出: 二级结构注释
- 接入方式: python / external
- 备注:
  - 适合作为结构报告的补充信息

---

## 2. 可视化工具(Visualization)

> 可视化工具用于 **展示实验结果**  
> 推荐用 **SummarizerAgent** 调用，而不是直接影响 Executor 流程

---

### 2.1 三维结构可视化(3D)

#### Mol*(Molstar)

- 类型: 网页端交互式 3D 结构可视化
- 输入: PDB文件
- 输出: HTML 页面中的交互视图
- 接入方式:
  - SummarizerAgent 生成 HTML 并嵌入 Mol*
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
  - Mol* 的可替代方案

#### PyMol

- 类型: 桌面级结构渲染工具
- 输入: PDB
- 输出: PNG / session 文件
- 接入方式:
  - python / subprocess 调用
- 备注:
  - 适合生成论文级静态图片
  - 不提供网页交互

---

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

---

## 3. Summarizer 可选择的工具（报告与汇总）

> Summarizer 的职责是：
> **将 Executor 的结果转化为“科研人员可理解的实验结果展示”**。

---

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
  - HTML 报告中可嵌入 Mol*、Plotly 图表
  - 不影响任务最终状态

#### PDF 导出（可选）
- 工具：wkhtmltopdf / playwright
- 输入：HTML 报告
- 输出：PDF
- 接入方式：external / nextflow
- 备注：
  - 用于提交或归档

---

### 3.2 结果对比与聚合

#### Pandas
- 类型：表格与结果聚合
- 输入：多个 StepResult / DesignResult
- 输出：对比表、统计数据
- 接入方式：python
- 备注：
  - 用于多候选结果对比
  - 可直接驱动可视化工具

---

## 4. 推荐的接入优先级（现实可行）
<!-- SID:tools.integration_priority -->

### P0（近期最值得接入）
- ESMFold（Executor）
- Mol*（Summarizer / Visualization）
- Matplotlib 或 Plotly（指标可视化）
- HTML 报告生成（Summarizer）

### P1（中期增强）
- PyMOL（静态渲染）
- MMseqs2 / BLAST（相似性分析）
- DSSP（二级结构）

### P2（远期扩展）
- AlphaFold / OpenFold
- 更复杂的序列 logo / MSA 可视化

---

## 5. 设计原则（约束）
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
- 结构预测类工具：
  - 支持多种执行后端：`nextflow`（本地）、`remote_model_service`（远程 API）
  - 同一能力可由多个工具提供（如 `esmfold` 和 `nim_esmfold` 均提供 `structure_prediction`）
  - Planner 通过 ProteinToolKG 选择合适的工具路径
- 远程模型服务（`remote_model_service`）：
  - 通过 Provider 配置系统管理 API 凭证与端点（见 `configs/model_providers.json`）
  - 失败码需映射到统一的 `FailureCode` 体系
  - 支持自动回退到本地工具（如 NIM 不可用时回退到 Nextflow）
<!-- SID:tools.adapter.constraints END -->
