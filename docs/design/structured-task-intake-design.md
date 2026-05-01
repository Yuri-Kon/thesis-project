---
doc_key: structured_task_intake
version: 0.1
status: draft
depends_on: [arch, agent, impl, algo, interface_surfaces, interface_web_workspace]
---

# 结构化任务输入与用户确认设计稿

> 本文档修正当前“仅从自然语言解析任务”的输入设计。目标是在不改变现有 FSM、Planner / Executor / Safety / Summarizer 边界、PendingAction / Decision 契约的前提下，为任务创建前增加一个可控、可审计、可确认的结构化输入层。

---

## 1. 背景与问题

当前实现路径大致为：

```text
用户自然语言 query -> TaskAPI -> Planner LLM 子模块解析 TaskSpec -> 规划
```

该路径的问题是：

- 自然语言直接进入 Planner，缺少明确的字段边界和用户确认；
- 必要属性、可选属性、默认值、模型推断值混在一起，难以审计；
- 用户无法在进入规划前纠正长度、任务类型、预算、工具偏好等关键约束；
- 前端和 CLI 难以提供稳定控件，只能提供“输入一段话”的弱约束体验；
- Planner 既承担意图解析又承担工具链规划，职责过宽。

修正方向是引入一个 **Task Intake（任务录入）层**：

```text
自然语言 / 表单 / CLI 参数
  -> TaskIntakeSession
  -> TaskSpecDraft（属性抽取、校验、缺口补齐）
  -> 用户确认
  -> ConfirmedTaskSpec
  -> POST /tasks 创建正式 Task
  -> CREATED -> PLANNING -> ...
```

Task Intake 是正式工作流之前的交互与数据准备阶段，不新增 `WAITING_*` 状态，也不替代现有 PendingAction / Decision。

---

## 2. 外部产品模式抽象

本设计参考现有对话式表单和 AI 产品的稳定做法，抽象为四条原则：

1. **Form / Slot Filling**
   - Rasa Forms 使用 required slots 收集完成任务所需字段；
   - Dialogflow CX 的 form parameters 明确区分 required、default value、reprompt；
   - 对本系统的启发：任务创建前应有字段注册表，先补齐必要字段，再进入规划。

2. **固定选项优先**
   - Bot Framework 的 ChoiceInput / ConfirmInput 将多选与确认建模为固定控件；
   - 对本系统的启发：任务类型、设计模式、预算档位、安全等级、工具偏好应优先用枚举、单选、多选、开关，而不是让用户自由描述。

3. **自然语言只做结构化抽取**
   - OpenAI Structured Outputs 等方案把模型输出约束到 JSON Schema；
   - 对本系统的启发：LLM 可以从自然语言抽取字段，但输出必须通过 schema、枚举、单位和置信度校验，不能直接成为 Planner 的隐式输入。

4. **确认后执行**
   - 对话式任务、订票、表单自动化产品通常在执行前展示“已理解内容”供用户确认；
   - 对本系统的启发：模型推断、默认值和用户显式输入必须可区分展示，只有确认后的 `ConfirmedTaskSpec` 才能创建正式 Task。

参考资料：

- Rasa Forms: https://rasa.com/docs/rasa/forms/
- Dialogflow CX Parameters: https://docs.cloud.google.com/dialogflow/cx/docs/concept/parameter
- OpenAI Structured Outputs: https://platform.openai.com/docs/guides/structured-outputs
- Microsoft Bot Framework Adaptive Inputs: https://learn.microsoft.com/en-us/azure/bot-service/adaptive-dialog/adaptive-dialog-prebuilt-inputs

---

## 3. 设计目标与非目标

### 3.1 目标

- 将用户输入拆成可验证的结构化属性；
- 将属性分为必要属性、条件必要属性、非必要属性；
- 对固定枚举字段提供选项控件；
- 保留自然语言输入能力，但只作为属性抽取入口；
- 在正式创建 Task 前提供确认、修改和补全流程；
- 把确认后的结构化任务交给 Planner，降低 Planner 对自由文本的依赖；
- 保持 Web 与 CLI 双入口语义一致；
- 保持所有输入来源、默认值、模型推断值、用户修改记录可审计。

### 3.2 非目标

- 不新增 Workflow FSM 状态；
- 不改变 `PendingAction / Decision` 用于计划、补丁、重规划确认的语义；
- 不新增 Agent 角色；
- 不让 PlannerAgent 直接等待用户输入；
- 不允许前端绕过 API 直接修改 Task 状态。

---

## 4. 核心对象

### 4.1 TaskIntakeSession

`TaskIntakeSession` 表示一次“任务创建前的录入会话”，它不等同于正式 Task。

```python
class TaskIntakeStatus(str, Enum):
    COLLECTING = "collecting"
    NEEDS_CONFIRMATION = "needs_confirmation"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
```

建议字段：

```json
{
  "intake_id": "intake_20260422_001",
  "status": "needs_confirmation",
  "raw_input": {
    "text": "设计一个约120 aa的稳定小蛋白...",
    "source": "web"
  },
  "draft": {},
  "missing_required_fields": [],
  "ambiguous_fields": [],
  "warnings": [],
  "created_at": "...",
  "updated_at": "..."
}
```

### 4.2 TaskSpecDraft

`TaskSpecDraft` 是可编辑、可解释的任务草稿。每个字段都必须保留来源和确认状态。

```json
{
  "task_kind": {
    "value": "de_novo_design",
    "source": "llm_extract",
    "confidence": 0.86,
    "confirmed": false
  },
  "length_range": {
    "value": [100, 140],
    "source": "llm_extract",
    "source_span": "约120 aa",
    "confidence": 0.91,
    "confirmed": false
  }
}
```

字段来源枚举：

- `user_explicit`：用户通过表单、CLI 参数或明确自然语言提供；
- `llm_extract`：模型从自然语言抽取；
- `system_default`：系统默认值；
- `kg_derived`：从 ToolKG 或能力注册表派生；
- `user_modified`：用户在确认页修改。

### 4.3 ConfirmedTaskSpec

`ConfirmedTaskSpec` 是唯一允许进入 `POST /tasks` 的结构化输入。

```json
{
  "goal": "设计一个稳定的小型 de novo 蛋白质候选",
  "constraints": {
    "task_kind": "de_novo_design",
    "objective_type": "stability",
    "length_range": [100, 140],
    "design_count": 8,
    "safety_level": "S1",
    "run_profile": "balanced",
    "require_plan_confirm": true
  },
  "initial_artifacts": [],
  "metadata": {
    "intake_id": "intake_20260422_001",
    "input_mode": "natural_language_with_confirmation",
    "confirmed_by": "user_001"
  }
}
```

Planner 只能把 `goal`、`constraints`、`initial_artifacts`、`metadata` 作为已确认输入；原始自然语言只可进入 `metadata.raw_query` 或审计记录，不得作为 Planner 的隐藏自由输入。

---

## 5. 蛋白质设计场景模板与字段注册表

字段注册表是 Task Intake 的核心。它定义每个字段的类型、控件、选项来源、是否必要、校验规则、默认值和 Planner 映射路径。

本系统不应把蛋白质设计输入建模为一个扁平表单。更合适的结构是：

```json
{
  "task_kind": "...",
  "objective": {},
  "inputs": {},
  "design_constraints": {},
  "quality_constraints": {},
  "structure_constraints": {},
  "function_constraints": {},
  "safety_constraints": {},
  "execution_preferences": {},
  "planner_policy": {}
}
```

其中：

- `task_kind` 决定任务场景；
- `objective` 描述优化目标；
- `inputs` 描述任务起点；
- `*_constraints` 描述设计、质量、结构、功能与安全约束；
- `execution_preferences` 描述运行成本、时延与精度偏好；
- `planner_policy` 描述 Planner 的确认策略和工具边界。

### 5.1 场景模板

第一版应按场景模板决定必填字段，而不是维护一组全局必填字段。场景模板必须标注支持等级：

- `P0`：当前系统主线应优先支持，可稳定进入 Planner；
- `P1`：中期增强，可先允许录入和审计，但 Planner 可降级处理；
- `P2`：远期扩展，只做 schema 预留或实验性入口。

| `task_kind` | 支持等级 | 场景含义 | 必填字段 | 常用可选字段 | Planner 能力提示 |
| --- | --- | --- | --- | --- | --- |
| `de_novo_design` | P0 | 从目标描述生成新的候选蛋白序列，并经过结构预测、QC 与排序 | `objective_type`、`goal_summary`、`length_range`、`design_count`、`run_profile`、`safety_level` | `motifs`、`min_plddt`、`max_runtime_min`、`tools_allowed`、`require_plan_confirm` | `sequence_generation`、`structure_prediction`、`quality_qc`、`objective_scoring` |
| `sequence_evaluation` | P0 | 对已有序列做结构预测、质量检查、物性或目标评分 | `input_sequence`、`objective_type`、`run_profile`、`safety_level` | `min_plddt`、`similarity_check_required`、`function_annotation_required` | `structure_prediction`、`quality_qc`、`objective_scoring` |
| `template_constrained_design` | P0/P1 | 基于已有结构模板或骨架设计/精修序列 | `template_pdb` 或 `template_artifact_ref`、`design_region`、`objective_type`、`run_profile`、`safety_level` | `fixed_positions`、`mutable_positions`、`motifs`、`rmsd_to_template_max` | `sequence_design`、`inverse_folding`、`structure_prediction`、`quality_qc` |
| `stability_optimization` | P1 | 在已有序列或结构基础上优化稳定性 | `input_sequence` 或 `template_pdb`、`optimization_target`、`mutation_budget`、`run_profile`、`safety_level` | `allowed_mutation_positions`、`min_plddt`、`max_hydrophobicity`、`simulation_required` | `sequence_design`、`physicochemical_scoring`、`stability_simulation` |
| `motif_scaffold_design` | P1/P2 | 保留关键 motif，在其周围生成或筛选 scaffold | `motifs`、`motif_position_policy`、`length_range`、`objective_type`、`run_profile`、`safety_level` | `template_pdb`、`fixed_positions`、`secondary_structure_preference` | `backbone_generation`、`sequence_generation`、`structure_prediction` |
| `binding_design` | P2 | 面向靶标、配体或蛋白互作的结合设计 | `target_description` 或 `target_structure`、`binding_site`、`objective_type=binding`、`run_profile`、`safety_level` | `ligand`、`interface_residues`、`docking_required` | `docking_scoring`、`objective_scoring`、`structure_prediction` |
| `enzyme_like_design` | P2 | 面向类酶功能、活性位点或反应类型的探索性设计 | `reaction_description` 或 `active_site_motif`、`objective_type=enzyme_like_activity`、`run_profile`、`safety_level` | `cofactor`、`substrate`、`EC_hint`、`motifs` | `function_annotation`、`objective_scoring`、`structure_prediction` |

说明：

- P0 场景应是第一版 Task Builder 和 Planner 的主要验收目标；
- P1/P2 场景可以先进入字段注册表，但 UI 应明确标注“增强/实验性”，Planner 在能力不足时必须给出可解释降级或拒绝；
- `binding_design`、`enzyme_like_design` 等场景对工具、数据和安全约束要求更高，不应在第一版承诺完整自动化。

### 5.2 字段分组与含义

#### 基础字段

| 字段 | 类型 | 含义 | 示例 | 说明 |
| --- | --- | --- | --- | --- |
| `task_kind` | enum | 任务场景类型 | `de_novo_design` | 决定条件必填字段和 Planner 能力提示 |
| `goal_summary` | string | 用户确认后的目标摘要 | “设计稳定小型蛋白” | 面向用户展示，也作为 Planner 的高层目标 |
| `objective_type` | enum/list | 主要优化目标 | `stability`、`structure_quality`、`binding` | 多目标任务可用 list，但必须指定主目标或权重 |
| `objective_weights` | object | 多目标权重 | `{"stability":0.6,"novelty":0.4}` | 未提供时由场景模板给默认值 |

#### 输入字段

| 字段 | 类型 | 含义 | 示例 | 说明 |
| --- | --- | --- | --- | --- |
| `input_sequence` | sequence | 已有氨基酸序列 | `MKT...` | 用于序列评估或优化起点 |
| `template_pdb` | artifact/path | 用户提供的结构模板 | `template.pdb` | 可来自上传文件或 artifact |
| `template_artifact_ref` | artifact ref | 已有任务产物引用 | `task_x/S2.pdb_path` | 必须可解析为已有 artifact |
| `motifs` | list[object] | 需要保留或偏好的序列/结构片段 | `{"sequence":"HExH","role":"active_site"}` | 可用于 motif scaffold 或约束设计 |
| `target_description` | string | 结合或功能设计的目标描述 | “结合某类小分子” | P2 场景常用，第一版不直接保证工具支持 |
| `target_structure` | artifact/path | 靶标结构文件 | `target.pdb` | binding 相关场景使用 |
| `ligand` | string/artifact | 小分子或配体信息 | SMILES / SDF | docking 相关场景使用 |

#### 设计空间约束

| 字段 | 类型 | 含义 | 示例 | 说明 |
| --- | --- | --- | --- | --- |
| `length_range` | int range | 允许的蛋白长度范围 | `[100, 140]` | de novo 场景 P0 必填 |
| `design_count` | int | 期望生成/保留的候选数量 | `8` | 影响生成规模和后续筛选成本 |
| `fixed_positions` | list[int] | 不允许突变的位置 | `[12, 35]` | 基于模板或已有序列时使用 |
| `mutable_positions` | list[int] | 允许设计的位置 | `[10, 11, 12]` | 与 `fixed_positions` 至少一方可指定 |
| `allowed_residues` | map/list | 指定位点允许的氨基酸集合 | `{"12":["A","V","L"]}` | 细粒度设计约束 |
| `forbidden_residues` | map/list | 禁止出现的氨基酸或位点规则 | `["C"]` | 可用于避免二硫键或特殊残基 |
| `mutation_budget` | int/range | 最大突变数量或比例 | `8` | 稳定性优化场景常用 |
| `design_region` | region/list | 设计区域 | `chain A:20-80` | template constrained 场景必填 |

#### 质量与结构约束

| 字段 | 类型 | 含义 | 示例 | 说明 |
| --- | --- | --- | --- | --- |
| `min_plddt` | float | 结构预测最低置信度 | `0.75` 或 `75` | 系统应统一归一化 |
| `qc_required` | bool | 是否必须经过质量门禁 | `true` | P0 默认 true |
| `max_low_complexity_ratio` | float | 最大低复杂度比例 | `0.25` | 防止无意义重复序列 |
| `max_hydrophobicity` | float | 疏水性上限 | `0.65` | 可由 objective_ranker 或 QC 使用 |
| `secondary_structure_preference` | enum/list | 二级结构偏好 | `alpha_helical` | 第一版可作为软约束 |
| `rmsd_to_template_max` | float | 与模板最大 RMSD | `2.0` | 模板约束设计常用 |
| `oligomeric_state` | enum | 单体/寡聚状态偏好 | `monomer` | 第一版可作为 metadata 或软约束 |
| `disulfide_policy` | enum | 二硫键策略 | `avoid`、`allow`、`require` | 影响 cysteine 相关约束 |

#### 功能与注释约束

| 字段 | 类型 | 含义 | 示例 | 说明 |
| --- | --- | --- | --- | --- |
| `function_description` | string | 用户期望功能的自然语言摘要 | “具有疏水口袋” | 可转为 objective scoring hint |
| `active_site_motif` | motif | 活性位点 motif | `HExH` | enzyme_like 场景使用 |
| `binding_site` | region/residue list | 结合位点约束 | `A:45,A:47,A:91` | binding 场景使用 |
| `interface_residues` | residue list | 蛋白互作界面残基 | `[45,47,91]` | P2 扩展 |
| `function_annotation_required` | bool | 是否需要功能注释/同源检索 | `true` | 触发 P1 工具能力 |
| `similarity_check_required` | bool | 是否需要相似性检索 | `true` | 可触发 MMseqs2/BLAST |
| `novelty_preference` | enum | 新颖性偏好 | `high` | 可作为相似性过滤软约束 |

#### 安全约束

| 字段 | 类型 | 含义 | 示例 | 说明 |
| --- | --- | --- | --- | --- |
| `safety_level` | enum | 安全策略等级 | `S0`、`S1` | 沿用既有语义 |
| `forbidden_functions` | list[string] | 明确禁止的功能方向 | `["toxin_like"]` | Safety 输入检查使用 |
| `organism` | string/enum | 来源或目标物种语境 | `E. coli` | 未提供则不限制 |
| `pathogenicity_related` | bool | 是否涉及病原相关语境 | `false` | Safety 预检查字段 |
| `toxicity_related` | bool | 是否涉及毒性相关语境 | `false` | Safety 预检查字段 |
| `dual_use_ack_required` | bool | 是否需要额外风险确认 | `false` | 由 Safety 或字段规则派生 |

#### 执行偏好与 Planner 策略

| 字段 | 类型 | 含义 | 示例 | 说明 |
| --- | --- | --- | --- | --- |
| `run_profile` | enum | 运行档位 | `fast_smoke`、`balanced`、`high_accuracy` | 只表达偏好，不直接选择工具 |
| `max_runtime_min` | int | 最大运行时间预算 | `60` | 可由 run_profile 推导 |
| `max_cost_level` | enum | 成本上限 | `low`、`medium`、`high` | 进入候选评分 |
| `allow_high_cost_tools` | bool/auto | 是否允许高代价工具 | `false` | `auto` 时由 Planner 判断 |
| `tools_allowed` | list[tool_id] | 工具白名单 | `["protgpt2","nim_esmfold"]` | 必须来自 ToolKG |
| `tools_excluded` | list[tool_id] | 工具黑名单 | `["openfold"]` | 必须来自 ToolKG |
| `require_plan_confirm` | bool | 初始 Plan 是否必须人工确认 | `true` | 与现有 `WAITING_PLAN_CONFIRM` 对齐 |
| `notes` | string | 用户备注 | “优先看稳定性” | 只进入 metadata，不作为硬约束 |

### 5.3 运行档位语义

`run_profile` 是执行偏好，不是工具选择。解析器只能把“快一点”“高精度”“先粗筛”等自然语言归一化为运行档位；具体工具链仍必须由 Planner 基于 ToolKG、I/O 闭包、成本/风险元数据和候选评分决定。

| `run_profile` | 语义 | 默认策略 |
| --- | --- | --- |
| `fast_smoke` | 快速验证，优先低延迟、低成本，适合先看可行性 | 较小 `design_count`，避免高代价工具，优先轻量 QC |
| `balanced` | 默认平衡模式，在质量、成本和时延之间折中 | 中等候选数，允许 Planner 选择必要的结构预测和 QC |
| `high_accuracy` | 高质量优先，接受更高成本和更长运行时间 | 较大候选数，允许高代价结构预测、增强评分或更多迭代 |

因此，“快一点的模式”应解析为：

```json
{
  "run_profile": {
    "value": "fast_smoke",
    "source": "llm_extract",
    "source_span": "快一点的模式",
    "confidence": 0.82
  }
}
```

不得解析为具体工具选择。

### 5.4 字段注册表模块

建议在实现层抽象 `TaskFieldRegistry` 模块，作为 Web、CLI、自然语言抽取、校验和 Planner 映射的共同来源。

该模块不应散落在前端常量、CLI 参数和 Planner prompt 中。建议使用可版本化配置，例如：

```yaml
version: 1
fields:
  length_range:
    group: design_constraints
    type: int_range
    ui_control: range_input
    nl_aliases: ["长度", "氨基酸数量", "aa", "residues"]
    validators:
      min: 20
      max: 1000
    maps_to: constraints.design_constraints.length_range

  run_profile:
    group: execution_preferences
    type: enum
    ui_control: segmented_control
    options: [fast_smoke, balanced, high_accuracy]
    default: balanced
    maps_to: constraints.execution_preferences.run_profile

task_profiles:
  de_novo_design:
    support_level: P0
    required:
      - objective_type
      - goal_summary
      - length_range
      - design_count
      - run_profile
      - safety_level
    optional:
      - motifs
      - min_plddt
      - tools_allowed
      - tools_excluded
      - require_plan_confirm
    capability_hints:
      - sequence_generation
      - structure_prediction
      - quality_qc
      - objective_scoring
```

`TaskFieldRegistry` 至少应提供以下能力：

- 生成 Web 表单 schema；
- 生成 CLI 参数与交互式问题；
- 生成 LLM 结构化抽取 schema；
- 计算当前 `task_kind` 下的必填字段和条件必填字段；
- 校验 enum、数值范围、artifact 引用、序列合法性和 ToolKG 工具 ID；
- 将 `TaskSpecDraft` 映射为 `ConfirmedTaskSpec`；
- 输出给 Planner 的 `capability_hints`、硬约束和软偏好；
- 标注字段支持等级，避免 P1/P2 字段被误认为 P0 可执行承诺。

字段新增流程：

1. 在 registry 中新增字段定义；
2. 指定所属 group、类型、控件、别名、校验器和 `maps_to`；
3. 将字段挂到一个或多个 `task_profiles`；
4. 若字段会影响 Planner，补充 `capability_hints` 或 Planner 映射测试；
5. 若字段需要 ToolKG 支持，先确认对应 capability / io_type / tool_id 已存在或标记为 P1/P2。

### 5.5 ConfirmedTaskSpec 推荐结构

确认后的结构应保留分组，而不是压平成单层 constraints：

```json
{
  "goal": "设计一个稳定的小型 de novo 蛋白质候选",
  "task_kind": "de_novo_design",
  "objective": {
    "objective_type": "stability",
    "objective_weights": {"stability": 0.7, "structure_quality": 0.3}
  },
  "inputs": {},
  "constraints": {
    "design_constraints": {
      "length_range": [100, 140],
      "design_count": 8
    },
    "quality_constraints": {
      "min_plddt": 0.75,
      "qc_required": true
    },
    "safety_constraints": {
      "safety_level": "S1"
    },
    "execution_preferences": {
      "run_profile": "fast_smoke",
      "max_runtime_min": 30
    },
    "planner_policy": {
      "require_plan_confirm": true,
      "tools_allowed": [],
      "tools_excluded": []
    }
  },
  "metadata": {
    "intake_id": "intake_20260422_001",
    "field_registry_version": 1,
    "support_level": "P0"
  }
}
```

Planner 可以在内部把上述结构投影到现有 `ProteinDesignTask.constraints` 字段，但不得丢失原始分组语义。

---

## 6. 自然语言解析流程

### 6.1 解析原则

自然语言解析器只允许输出 `TaskSpecDraft`，不得直接创建 Plan。

解析器必须满足：

- 使用固定 JSON Schema；
- 枚举字段只能输出注册表允许值；
- 数值字段必须带单位归一化；
- 每个字段必须带 `source`、`confidence`、可选 `source_span`；
- 低置信度字段进入 `ambiguous_fields`；
- 未识别内容进入 `unmapped_text`，不得静默丢弃；
- schema 不合法时重试有限次数，仍失败则降级为手动表单。

### 6.2 置信度门槛

建议第一版固定阈值：

- `confidence >= 0.80`：可作为候选填充值，但仍需展示确认；
- `0.50 <= confidence < 0.80`：标记为 ambiguous，要求用户确认或改写；
- `confidence < 0.50`：不填入字段，只保留在 unmapped_text；
- 任何必要字段即使高置信度抽取成功，也必须在确认页展示。

### 6.3 解析输出示例

输入：

```text
帮我设计一个大约120个氨基酸、稳定性优先的小蛋白，先用快一点的模式，最后需要我确认计划。
```

输出：

```json
{
  "fields": {
    "task_kind": {"value": "de_novo_design", "confidence": 0.84, "source": "llm_extract"},
    "objective_type": {"value": "stability", "confidence": 0.88, "source": "llm_extract"},
    "length_range": {"value": [100, 140], "confidence": 0.91, "source": "llm_extract", "source_span": "大约120个氨基酸"},
    "run_profile": {"value": "fast_smoke", "confidence": 0.82, "source": "llm_extract"},
    "require_plan_confirm": {"value": true, "confidence": 0.95, "source": "llm_extract"}
  },
  "missing_required_fields": [],
  "ambiguous_fields": [],
  "unmapped_text": []
}
```

---

## 7. 用户确认流程

### 7.1 状态流程

Task Intake 的流程独立于正式 Task FSM：

```text
COLLECTING
  -> NEEDS_CONFIRMATION
  -> CONFIRMED
  -> create Task(CREATED)
```

若必要字段缺失：

```text
COLLECTING
  -> COLLECTING（继续补字段）
  -> NEEDS_CONFIRMATION
```

取消录入只会取消 `TaskIntakeSession`，不会生成正式 Task，也不使用 `CANCELLED` 工作流终态。

### 7.2 确认页必须展示

- 用户原始输入；
- 系统理解出的目标摘要；
- 必要字段及其来源；
- 条件必要字段及其补齐状态；
- 默认值列表；
- 低置信度或歧义字段；
- 未映射文本；
- Safety 输入预检查结果；
- “确认创建任务”按钮。

### 7.3 确认规则

只有满足以下条件才能生成 `ConfirmedTaskSpec`：

- 所有必要字段已填写；
- 所有条件必要字段已满足；
- 所有 enum/list 字段均来自注册表或 ToolKG；
- 所有数值字段通过范围与单位校验；
- Safety 输入预检查未返回 `block`；
- 用户显式确认。

若 Safety 输入预检查返回 `warn`，确认页必须展示风险摘要，并要求用户显式勾选“已理解风险提示”；该确认记录进入 `metadata` 和审计日志。

---

## 8. API 设计

### 8.1 创建录入会话

```http
POST /task-intakes
```

请求：

```json
{
  "text": "设计一个约120 aa的稳定小蛋白",
  "structured_fields": {
    "run_profile": "balanced"
  },
  "source": "web"
}
```

响应：

```json
{
  "intake_id": "intake_20260422_001",
  "status": "needs_confirmation",
  "draft": {},
  "missing_required_fields": [],
  "ambiguous_fields": []
}
```

### 8.2 更新字段

```http
PATCH /task-intakes/{intake_id}
```

请求：

```json
{
  "fields": {
    "length_range": [100, 140],
    "run_profile": "balanced"
  }
}
```

服务端重新运行字段校验、条件必要字段检查与 Safety 输入预检查。

### 8.3 获取字段注册表

```http
GET /task-intakes/schema
```

响应应包含：

- 字段定义；
- enum options；
- 条件必要规则；
- 默认值；
- 控件建议；
- ToolKG 派生的工具选项。

Web 和 CLI 都必须以该接口为准，不能硬编码选项。

### 8.4 确认并创建正式任务

```http
POST /task-intakes/{intake_id}/confirm
```

请求：

```json
{
  "confirmed_by": "user_001",
  "acknowledged_warnings": ["SAFETY_INPUT_WARN_001"]
}
```

响应：

```json
{
  "intake_id": "intake_20260422_001",
  "task_id": "task_20260422_001",
  "status": "CREATED"
}
```

副作用：

- 将 `TaskIntakeSession.status` 标记为 `CONFIRMED`；
- 写入 `ConfirmedTaskSpec`；
- 创建正式 Task；
- 将 intake 摘要写入 Task metadata；
- 追加任务创建事件，例如 `TASK_CREATED_FROM_CONFIRMED_INTAKE`。

### 8.5 兼容旧接口

旧的 `POST /tasks` 可保留，但应逐步收敛为两种模式：

1. 接收 `confirmed_task_spec`，用于正式创建任务；
2. 若仍收到自由文本 `query`，内部自动创建 `TaskIntakeSession`，返回 `intake_id` 和 `needs_confirmation`，而不是直接进入规划。

---

## 9. Web 交互设计

Web 端新增 Task Builder 工作区，作为正式 Task 创建前的入口。

### 9.1 输入区

支持两种等价入口：

- 自然语言输入框：用户描述目标；
- 结构化表单：用户直接选择任务类型、目标、长度、运行档位等。

两种入口写入同一份 `TaskSpecDraft`。

### 9.2 字段确认区

建议布局：

- 左侧：原始输入与未映射文本；
- 中央：必要字段表单；
- 右侧：默认值、风险提示、创建按钮；
- 高级区：工具白名单、质量阈值、预算上限等非必要字段。

字段 UI 规则：

- enum 使用单选或分段控件；
- list enum 使用多选；
- bool 使用 toggle；
- 数值范围使用双输入或范围控件；
- artifact 使用上传或已有 artifact picker；
- 低置信度字段显示“需要确认”标记；
- 模型推断字段显示来源片段。

### 9.3 创建后的衔接

确认创建后跳转到 Task Detail。若任务进入 `WAITING_PLAN_CONFIRM`，继续使用现有 Pending Review 工作区处理计划确认。

---

## 10. CLI 交互设计

CLI 保持无头环境最小闭环：

```text
design intake parse --text "设计一个约120 aa的稳定小蛋白"
design intake show <intake_id>
design intake set <intake_id> --length-range 100:140 --run-profile balanced
design intake confirm <intake_id>
```

也可提供交互式快捷入口：

```text
design submit --interactive
```

CLI 输出必须清楚区分：

- 已确认字段；
- 待补字段；
- 低置信度字段；
- 默认字段；
- Safety warn；
- 确认后生成的 task_id。

脚本化场景可以使用：

```text
design submit --spec task_spec.json --confirm
```

其中 `task_spec.json` 必须符合 `ConfirmedTaskSpec` schema。

---

## 11. 与现有 Agent / FSM / HITL 的关系

### 11.1 FSM

Task Intake 不属于正式 Task FSM。正式 Task 仍从 `CREATED` 开始，继续遵循：

```text
CREATED -> PLANNING -> ... -> DONE / FAILED / CANCELLED
```

不得引入 `WAITING_INPUT_CONFIRM` 这类新工作流状态。

### 11.2 PlannerAgent

PlannerAgent 的输入从“自由 query 为主”调整为“ConfirmedTaskSpec 为主”。

Planner 可以读取：

- `goal`
- `constraints`
- `initial_artifacts`
- `metadata.intake_summary`

Planner 不得：

- 再次向用户追问字段；
- 直接使用未经确认的自然语言覆盖结构化字段；
- 从 prompt 中推断 ToolKG 外工具。

### 11.3 SafetyAgent

SafetyAgent 在 Task Intake 确认前执行输入预检查：

- `block`：不得确认创建正式 Task；
- `warn`：允许用户确认后继续，但必须记录 acknowledgement；
- `ok`：正常确认。

正式 Task 进入执行后，SafetyAgent 仍按既有输入、步骤、输出阶段工作。

### 11.4 PendingAction / Decision

Task Intake 的确认不是 `PendingAction / Decision`。

原因：

- PendingAction 用于正式 Task 进入 `WAITING_*` 后的计划、补丁、重规划决策；
- Task Intake 发生在正式 Task 创建前；
- 混用会让 `WAITING_*` 语义变得模糊。

但两者在 UI 风格上可以一致：都展示候选、解释、风险和确认按钮。

---

## 12. 校验与审计

### 12.1 校验层次

1. JSON Schema / Pydantic 类型校验；
2. 字段注册表 enum 校验；
3. 条件必要字段校验；
4. 单位归一化与范围校验；
5. ToolKG 工具 ID 校验；
6. Safety 输入预检查；
7. 用户确认校验。

### 12.2 审计事件

建议新增 intake 级审计事件：

- `INTAKE_CREATED`
- `INTAKE_PARSED`
- `INTAKE_FIELD_UPDATED`
- `INTAKE_SAFETY_CHECKED`
- `INTAKE_CONFIRMED`
- `INTAKE_CANCELLED`
- `TASK_CREATED_FROM_CONFIRMED_INTAKE`

正式 Task 创建后，Task EventLog 至少应能回链到 `intake_id`。

---

## 13. 落地里程碑

### M1：Schema 与服务端闭环

- 定义 `TaskIntakeSession`、`TaskSpecDraft`、`ConfirmedTaskSpec`；
- 实现字段注册表；
- 实现 `/task-intakes/schema`、`POST /task-intakes`、`PATCH /task-intakes/{id}`、`confirm`；
- `POST /tasks` 接收 `ConfirmedTaskSpec`。

### M2：自然语言结构化抽取

- 使用结构化输出 schema 抽取字段；
- 加入置信度、source_span、unmapped_text；
- 抽取失败降级到手动表单。

### M3：Web Task Builder

- 实现自然语言输入 + 结构化确认表单；
- 支持必要字段补齐、默认值展示、Safety warn acknowledgement；
- 确认后跳转 Task Detail。

### M4：CLI Intake

- 实现 `design intake parse/show/set/confirm`；
- 支持 `design submit --interactive`；
- 支持 `--spec task_spec.json --confirm`。

### M5：Planner 收敛

- Planner 输入改为以 `ConfirmedTaskSpec` 为准；
- 原自然语言 query 仅作为 metadata 与审计信息；
- 补充测试确保 Planner 不依赖未确认自由文本。

---

## 14. 测试要求

至少覆盖：

- 必要字段缺失时不能 confirm；
- 条件必要字段随 `task_kind` / `objective_type` 正确变化；
- enum 非法值被拒绝；
- ToolKG 外工具 ID 被拒绝；
- 自然语言抽取低置信度字段进入 ambiguous；
- Safety `block` 时不能创建正式 Task；
- Safety `warn` 时必须 acknowledgement；
- confirm 后创建 Task 且状态从 `CREATED` 开始；
- confirm 后 Task metadata 可回链 `intake_id`；
- 旧 `POST /tasks` 自由文本路径不再绕过确认。

---

## 15. 设计结论

本方案将“自然语言理解”从 Planner 的隐式前置步骤中拆出，变成一个可见、可编辑、可确认的 Task Intake 层。

最终效果是：

- 用户可以继续用自然语言表达目标；
- 系统先抽取结构化属性；
- 必要属性和非必要属性被明确区分；
- 固定选项由注册表和 ToolKG 提供；
- 用户确认后才创建正式 Task；
- Planner 只消费确认后的结构化任务；
- 现有 FSM、HITL、PendingAction / Decision 和 Agent 边界保持不变。
