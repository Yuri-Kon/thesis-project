# SciToolAgent 实验工具接入说明

本文说明如何在本项目中接入 SciToolAgent / SciToolEval 实验涉及的工具。结论先行：

- 本项目当前工具体系面向蛋白设计，核心链路是 `ToolKG -> Planner -> PlanStep.tool -> AdapterRegistry -> BaseToolAdapter -> StepResult`。
- SciToolEval 数据集覆盖 531 个问题、150 个唯一工具名，主要集中在小分子格式转换、RDKit 分子描述符、外部化学数据库、少量蛋白/DNA 序列工具和材料数据库工具。
- 推荐接入方式不是为 150 个工具分别写 150 个适配器，而是先按执行后端聚合为 5 类 adapter：`rdkit_chem`、`chem_identifier_resolver`、`chem_safety_lookup`、`bioseq_tools`、`materials_lookup`，再在 adapter 内按 SciToolAgent 原始工具名分发。

## 1. 现有项目中的工具接入机制

本项目已有工具接入机制位于以下文件：

- `src/adapters/base_tool_adapter.py`：所有工具适配器的抽象基类，要求实现 `resolve_inputs()` 和 `run_local()`；如需要远程执行，可额外实现 `run_remote()`。
- `src/adapters/registry.py`：工具注册表，按 `tool_id` 或 `adapter_id` 查找 adapter。
- `src/adapters/builtins.py`：启动时注册内置 adapter。
- `src/workflow/step_runner.py`：Executor 执行单步计划时，通过 `get_adapter(step.tool)` 获取 adapter，然后执行工具。
- `src/models/contracts.py`：`PlanStep.tool` 是工具身份，必须能对应 ToolKG 中的 `tool.id`；`StepResult` 记录统一输出、指标和执行元数据。
- `src/kg/protein_tool_kg.json`：当前默认 ToolKG，Planner 从其中加载工具注册表。
- `configs/tool_metadata/active_tool_metadata.json`：运行期成本、风险、可靠性等工具元数据，用于候选排序和实验分析。

因此，一个工具要被 Planner 和 Executor 正常使用，需要同时满足三件事：

1. ToolKG 中存在工具节点，`id` 与计划中的 `PlanStep.tool` 一致。
2. `src/adapters/builtins.py` 或运行初始化逻辑注册了同名 adapter。
3. adapter 输出字段与 ToolKG 的 `io.outputs`、下游步骤引用和 `StepResult.outputs` 保持一致。

## 2. SciToolEval 工具需求概览

本地 SciToolEval 数据来自：

- `deliverables/scitoolagent-reference-dataset/SciToolAgent/SciToolEval/data/level1_question.jsonl`
- `deliverables/scitoolagent-reference-dataset/SciToolAgent/SciToolEval/data/level2_question.jsonl`

统计结果：

- 问题总数：531
- 唯一工具名：150
- 单题工具链长度：1 到 11 步
- 高频工具：`NameToSMILES`、`InChIKeyToSMILES`、`SlnToSmiles`、`SELFIEStoSMILES`、`GetChi1v`、`GetKappa1`、`GetCrippenDescriptors`、`GetKappa2`、`SMILESToCAS`、`GetMolFormula`

按能力聚合后，实验工具可分为以下几类。

| 类别 | 代表工具 | 推荐后端 |
| --- | --- | --- |
| 小分子标识与格式转换 | `NameToSMILES`、`InChIKeyToSMILES`、`SMILESToInChI`、`InChIToInChIKey`、`SELFIEStoSMILES`、`SMILEStoSELFIES`、`SlnToSmiles` | PubChem / ChemSpider / RDKit / SELFIES |
| RDKit 描述符与结构分析 | `GetChi1v`、`GetKappa1`、`CalculateTPSA`、`GetCrippenDescriptors`、`GetMolFormula`、`GetRingsNum`、`GetMACCSKeysFingerprint` | RDKit |
| 化学安全与外部属性查询 | `SafetySummary`、`CheckExplosiveness`、`SMILESToCAS`、`CASToPrice` | 本地 CSV / PubChem / ChemSpider / 可选第三方 API |
| 蛋白/DNA 序列工具 | `AnalyzeProteinSeqFromPDB`、`DoubleSequenceGlobalAlignment`、`ProteinMotifAnalysis`、`TranslateDNAtoAminoAcidSequence` | Biopython / PDB REST |
| 材料数据库工具 | `GetBandGapByFormula`、`GetBandGapByMaterialId`、`IsStableByFormula`、`GetDensityByMaterialId` | Materials Project API / 本地缓存 |

当前项目已经支持蛋白设计相关工具，例如 `protgpt2`、`protein_mpnn`、`esmfold`、`openfold`、`biopython_qc`、`dssp`、`blastp`、`mmseqs2`、`foldseek`、`interproscan`、`mda_analysis`、`autodock_vina`。这些工具与 SciToolEval 中的小分子/材料工具不是同一套命名体系，需要新增一组 SciToolAgent 兼容工具节点。

## 3. 推荐的总体接入方案

### 3.1 保留 SciToolAgent 原始工具名

SciToolEval 的标准答案中直接使用原始工具名作为 `tool_path`，例如：

```json
{
  "tool_path": ["SMILESToInChI", "InChIToInChIKey"],
  "question": "What is the InChIKey for the molecule represented by the SMILES notation ..."
}
```

为了能直接评估工具路径，建议 ToolKG 中的 `tool.id` 直接采用 SciToolAgent 原始工具名，而不是改成蛇形命名。例如使用 `NameToSMILES`，不要改成 `name_to_smiles`。这样 `eval_tool_path.py` 可以直接比较预测工具链和标准工具链。

### 3.2 用少量 adapter 承载大量同类工具

虽然 ToolKG 可以有 150 个工具节点，但 adapter 不需要 150 个类。建议做一层分发：

| Adapter | 覆盖工具 | 主要职责 |
| --- | --- | --- |
| `SciToolAgentChemAdapter` | RDKit 描述符、SMILES/SELFIES/InChI 转换 | 本地纯 Python / RDKit 执行 |
| `SciToolAgentIdentifierAdapter` | `NameToSMILES`、`InChIKeyToSMILES`、`SMILESToCAS` | 调 PubChem/ChemSpider 或读本地缓存 |
| `SciToolAgentSafetyAdapter` | `SafetySummary`、`CheckExplosiveness`、`CASToPrice` | 查询 `toxin_compound.csv`、`toxin_protein.csv` 或外部数据库 |
| `SciToolAgentBioSeqAdapter` | PDB 序列、DNA 翻译、序列比对、蛋白 motif | Biopython / PDB REST / 本地规则 |
| `SciToolAgentMaterialsAdapter` | band gap、density、stability、crystal system | Materials Project API 或本地缓存 |

具体注册时，每个 SciToolAgent 工具名仍需可被 `get_adapter(tool_id)` 找到。可以通过两种方式实现：

1. 为每个工具名注册同一个 adapter 实例，但设置不同 `adapter_id`。
2. 写一个轻量 wrapper 类，`tool_id` 是 SciToolAgent 原始工具名，内部委托到同一个 backend dispatcher。

第二种更清晰，也更符合当前 `AdapterRegistry` 对 `tool_id` 唯一性的约束。

## 4. 代码接入步骤

### 4.1 新增 adapter 目录或文件

建议新增：

```text
src/adapters/scitoolagent/
├── __init__.py
├── base.py
├── chem_adapter.py
├── identifier_adapter.py
├── safety_adapter.py
├── bioseq_adapter.py
└── materials_adapter.py
```

如果希望改动更小，也可以先放在单文件：

```text
src/adapters/scitoolagent_adapter.py
```

最小 adapter 结构如下：

```python
from __future__ import annotations

from time import perf_counter
from typing import Any, Dict, Tuple

from src.adapters.base_tool_adapter import BaseToolAdapter
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext


class SciToolAgentToolAdapter(BaseToolAdapter):
    tool_id: str
    adapter_id: str

    def __init__(self, tool_id: str) -> None:
        self.tool_id = tool_id
        self.adapter_id = f"scitoolagent:{tool_id}"

    def resolve_inputs(
        self,
        step: PlanStep,
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}
        for key, value in step.inputs.items():
            if isinstance(value, str) and "." in value:
                step_id, field = value.split(".", 1)
                if step_id.startswith("S") and context.has_step_result(step_id):
                    resolved[key] = context.get_step_output(step_id, field)
                    continue
            resolved[key] = value
        return resolved

    def run_local(
        self,
        inputs: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        started = perf_counter()
        result = dispatch_scitoolagent_tool(self.tool_id, inputs)
        return (
            {
                "result": result,
                "value": result,
                "tool_name": self.tool_id,
            },
            {
                "exec_type": "python",
                "duration_ms": int((perf_counter() - started) * 1000),
                "tool_id": self.tool_id,
                "adapter_id": self.adapter_id,
            },
        )
```

注意：正式实现时应避免 `Any`，需要根据本项目 typing baseline 定义更精确的输入输出类型；上面只是说明接入形态。

### 4.2 实现工具分发函数

建议在 adapter 内部将工具分成不同 backend：

```python
def dispatch_scitoolagent_tool(tool_id: str, inputs: Mapping[str, object]) -> object:
    if tool_id in RDKIT_TOOL_IDS:
        return run_rdkit_tool(tool_id, inputs)
    if tool_id in IDENTIFIER_TOOL_IDS:
        return run_identifier_tool(tool_id, inputs)
    if tool_id in SAFETY_TOOL_IDS:
        return run_safety_tool(tool_id, inputs)
    if tool_id in BIOSEQ_TOOL_IDS:
        return run_bioseq_tool(tool_id, inputs)
    if tool_id in MATERIALS_TOOL_IDS:
        return run_materials_tool(tool_id, inputs)
    raise StepRunError(...)
```

输入字段建议统一为：

- `parameter`：来自 SciToolEval 的 `Parameter` 字段，原始输入。
- `value`：上游步骤输出的默认值。
- `smiles`、`inchi`、`inchikey`、`selfies`、`sln`、`sequence`、`material_id`、`formula`：按工具类型展开的结构化输入。

输出字段建议统一包含：

- `result`：默认答案值，便于后续步骤用 `S1.result` 引用。
- `value`：同 `result`，兼容更通用的步骤引用。
- 与工具语义对应的字段，例如 `smiles`、`inchi`、`inchikey`、`formula`、`descriptor_value`、`safety_summary`。

例如：

| 工具 | 输入 | 输出 |
| --- | --- | --- |
| `NameToSMILES` | `name` 或 `parameter` | `smiles`、`result` |
| `SMILESToInChI` | `smiles` 或 `value` | `inchi`、`result` |
| `InChIToInChIKey` | `inchi` 或 `value` | `inchikey`、`result` |
| `GetMolFormula` | `smiles` 或 `value` | `formula`、`result` |
| `CalculateTPSA` | `smiles` 或 `value` | `tpsa`、`descriptor_value`、`result` |
| `SafetySummary` | `smiles`、`cas` 或 `value` | `safety_summary`、`result` |

### 4.3 注册 adapter

在 `src/adapters/builtins.py` 中新增注册逻辑：

```python
from src.adapters.scitoolagent_adapter import (
    SCITOOLAGENT_TOOL_IDS,
    SciToolAgentToolAdapter,
)


def ensure_builtin_adapters() -> None:
    ...
    for tool_id in SCITOOLAGENT_TOOL_IDS:
        try:
            get_adapter(tool_id)
        except KeyError:
            register_adapter(SciToolAgentToolAdapter(tool_id))
```

这一步完成后，Executor 才能通过 `PlanStep.tool = "NameToSMILES"` 找到对应 adapter。

### 4.4 扩展 ToolKG

当前 Planner 默认从 `src/kg/protein_tool_kg.json` 加载工具。接入 SciToolAgent 工具时有两种选择：

1. 在现有 KG 中追加 SciToolAgent 工具节点。优点是改动小；缺点是蛋白设计工具和化学/材料工具会混在同一个 KG。
2. 新增 `src/kg/scitoolagent_tool_kg.json`，并让实验入口显式传入该 KG。优点是边界清楚；缺点是需要扩展 KG 加载路径配置。

为了尽快跑通 SciToolEval，建议第一阶段采用方案 1，追加工具节点，并通过任务约束 `tools_allowed` 控制实验工具范围。工具节点模板如下：

```json
{
  "id": "NameToSMILES",
  "tool_id": "NameToSMILES",
  "name": "NameToSMILES",
  "domain": "chemistry/identifier",
  "description": "Resolve a molecule name to a SMILES string.",
  "capabilities": ["chemical_identifier_resolution"],
  "io": {
    "io_type_id": "name_to_smiles",
    "inputs": {"name": "str"},
    "outputs": {"smiles": "str", "result": "str"},
    "input_types": ["molecule_name"],
    "output_types": ["smiles"],
    "combinable": true
  },
  "constraints": {
    "preconditions": ["name_provided"],
    "resource_assumptions": ["pubchem_or_local_cache_ready"],
    "limits": {}
  },
  "execution": "python",
  "cost_score": 0.25,
  "safety_level": 1,
  "priority": "P1",
  "failure_modes": ["not_found", "ambiguous_name", "network_error"],
  "preferred_next": ["GetMolFormula", "CalculateTPSA", "SMILESToInChI"],
  "version": "1.0.0"
}
```

同时需要新增 capability 和 io_type，例如：

```json
{
  "capability_id": "chemical_identifier_resolution",
  "name": "Chemical Identifier Resolution",
  "domain": "chemistry/identifier",
  "description": "Resolve molecule names, InChI, InChIKey, CAS, SMILES, SELFIES and related identifiers."
}
```

### 4.5 扩展运行期工具元数据

在 `configs/tool_metadata/active_tool_metadata.json` 中追加 SciToolAgent 工具的成本/风险元数据。为了不手写 150 个初始条目，可先按类别赋默认值：

| 类别 | compute_cost_prior | latency_cost_prior | reliability_prior | high_cost_flag |
| --- | ---: | ---: | ---: | --- |
| RDKit 本地描述符 | 0.10 | 0.10 | 0.88 | false |
| 本地格式转换 | 0.08 | 0.08 | 0.90 | false |
| 外部标识解析 | 0.20 | 0.45 | 0.72 | false |
| 安全/价格查询 | 0.20 | 0.50 | 0.70 | false |
| 材料数据库查询 | 0.25 | 0.55 | 0.72 | false |
| 蛋白/DNA 序列工具 | 0.18 | 0.20 | 0.82 | false |

后续如果发现某些 API 限流或失败率高，再调高 `execution_risk_prior` 和 `latency_cost_prior`。

## 5. 依赖与环境变量

建议新增依赖：

```bash
uv add rdkit selfies pubchempy
```

如果使用 ChemSpider、Materials Project 或其他商业/学术 API，需要通过环境变量配置，不要写入代码或日志：

```bash
export CHEMSPIDER_API_KEY=...
export MATERIALS_PROJECT_API_KEY=...
```

可选依赖：

- `rdkit`：多数小分子描述符、指纹、分子性质。
- `selfies`：SMILES / SELFIES 互转。
- `pubchempy`：名称、CID、SMILES、InChI 等公开查询。
- `mp-api`：Materials Project 查询。
- `biopython`：序列比对、PDB 解析、DNA 翻译；本项目已包含。

## 6. 数据文件接入

本地 SciToolAgent 数据包中包含：

- `data/tool_example.xlsx`：SciToolAgent 工具 KG 示例表。
- `data/toxin_compound.csv`：毒性/安全相关小分子数据。
- `data/toxin_protein.csv`：毒性/安全相关蛋白数据。
- `SciToolEval/data/*.jsonl`：评测问题、标准答案和标准工具路径。

建议将这些文件作为只读参考数据放入项目数据目录，例如：

```text
data/scitoolagent/
├── tool_example.xlsx
├── toxin_compound.csv
├── toxin_protein.csv
└── SciToolEval/
    └── data/
```

adapter 中不要硬编码绝对路径，应通过配置或环境变量传入：

```bash
export SCITOOLAGENT_DATA_DIR=data/scitoolagent
```

## 7. SciToolEval 运行方式

接入后，建议新增一个实验入口，将 SciToolEval JSONL 转成项目任务：

```text
scripts/run_scitooleval.py
```

转换规则：

| SciToolEval 字段 | 本项目字段 |
| --- | --- |
| `question` | `ProteinDesignTask.goal` 或通用任务 `goal` |
| `Parameter` | `constraints.scitoolagent_parameter` |
| `tool_path` | `metadata.expected_tool_path`，用于评估，不应直接泄露给 Planner |

如果要做“工具路径复现”实验，可以把 `tool_path` 显式转成 `Plan.steps`：

```json
{
  "task_id": "scitooleval_level2_0001",
  "steps": [
    {
      "id": "S1",
      "tool": "SMILESToInChI",
      "inputs": {"smiles": "<Parameter>"}
    },
    {
      "id": "S2",
      "tool": "InChIToInChIKey",
      "inputs": {"inchi": "S1.result"}
    }
  ]
}
```

如果要做“自主规划”实验，则不应把标准 `tool_path` 提供给 Planner，只把 `question` 和 `Parameter` 作为输入，最后用 SciToolEval 的 `eval_tool_path.py` 和 `eval_accuracy.py` 评价结果。

## 8. 验证方案

建议分三层验证：

1. 单工具单测：每个 adapter 类至少覆盖成功、非法输入、查不到结果三类情况。
2. 工具链集成测试：选取 SciToolEval 中高频链路，例如 `NameToSMILES -> GetMolFormula -> CalculateTPSA`。
3. 评测脚本对齐：输出格式匹配 SciToolEval 的 `example_standard_answer.jsonl` 和 `example_standard_toolpath.jsonl`。

推荐最小测试集：

| 测试目标 | 示例 |
| --- | --- |
| 格式转换 | `SMILESToInChI -> InChIToInChIKey` |
| 名称解析 | `NameToSMILES -> GetMolFormula` |
| RDKit 描述符 | `NameToSMILES -> GetChi1v -> CalculateTPSA` |
| SELFIES | `SMILEStoSELFIES -> SELFIEStoSMILES` |
| 安全查询 | `SMILESToCAS -> CheckExplosiveness` |
| 蛋白序列 | `AnalyzeProteinSeqFromPDB` |
| 材料查询 | `GetBandGapByMaterialId` |

项目侧验证命令：

```bash
uv run pytest tests/unit/test_scitoolagent_adapter.py
uv run basedpyright src/adapters/scitoolagent_adapter.py tests/unit/test_scitoolagent_adapter.py
```

SciToolEval 侧验证命令：

```bash
cd deliverables/scitoolagent-reference-dataset/SciToolAgent/SciToolEval/eval
python eval_accuracy.py \
  --input_file <agent_answer.jsonl> \
  --standard_file ../data/level1_correct_answer.jsonl \
  --output_file <accuracy_result.jsonl>

python eval_tool_path.py \
  --input_file <agent_toolpath.jsonl> \
  --standard_file ../data/level1_question.jsonl \
  --tool_description_file <tool_description.json> \
  --output_file <toolpath_result.jsonl>
```

## 9. 分阶段实施建议

### 第一阶段：跑通高频化学工具

优先覆盖出现频次最高、依赖最少的工具：

- `NameToSMILES`
- `InChIKeyToSMILES`
- `SlnToSmiles`
- `SELFIEStoSMILES`
- `SMILEStoSELFIES`
- `SMILESToInChI`
- `InChIToInChIKey`
- `GetMolFormula`
- `CalculateTPSA`
- `GetChi1v`
- `GetKappa1`
- `GetCrippenDescriptors`

这一阶段主要依赖 RDKit、SELFIES、PubChem 或本地缓存，可覆盖 SciToolEval 中相当多的链路。

### 第二阶段：补齐安全查询和蛋白/DNA 工具

接入：

- `SafetySummary`
- `CheckExplosiveness`
- `SMILESToCAS`
- `AnalyzeProteinSeqFromPDB`
- `DoubleSequenceGlobalAlignment`
- `DoubleSequenceLocalAlignment`
- `TranslateDNAtoAminoAcidSequence`
- `ProteinMotifAnalysis`

其中安全类工具应优先走本地 `toxin_compound.csv`、`toxin_protein.csv`，外部 API 只作为补充。

### 第三阶段：补齐材料数据库工具

接入 Materials Project 相关工具：

- `GetBandGapByFormula`
- `GetBandGapByMaterialId`
- `GetCrystalSystemByMaterialId`
- `GetDensityByMaterialId`
- `GetEnergyAboveHullByMaterialId`
- `IsStableByFormula`
- `IsStableByMaterialId`

该阶段强依赖 API key 和网络环境

## 10. 风险与注意事项

- SciToolAgent 原始仓库 README 提到完整工具服务目录为 `tools/ToolsFuns`，但当前本地参考包主要包含数据、评测脚本和入口文件；若要 1:1 复刻原实现，需要另行获取完整工具服务代码。
- SciToolEval 的工具名大小写敏感，接入时应保留原始名称，否则工具路径评估会受影响。
- 外部数据库查询会带来网络失败、限流和结果歧义，必须在 adapter 中转成统一失败类型，并让 Planner 有 fallback。
- 不要把 API key、数据库 token、请求原始响应中的敏感字段写入事件日志。
- 不能让 adapter 自行改变 workflow 状态；adapter 只返回输出或抛出可分类异常，状态转换仍由 `PlanRunner` / `StepRunner` 管理。

## 附录：SciToolEval 当前出现的工具名

括号中为该工具在 `level1_question.jsonl` 和 `level2_question.jsonl` 的标准工具路径中出现的次数。

### RDKit/分子描述符与结构分析

`AddHydrogens(3)`、`AssignOxidationNumbers(2)`、`AssignPattyTypes(2)`、`BuildAtomPairFpFromSmiles(2)`、`BuildAvalonFpFromSmiles(2)`、`BuildMorganFpFromSmiles(3)`、`BuildRdkitFpFromSmiles(1)`、`CalculateEstateIndices(2)`、`CalculateEstateVsa(4)`、`CalculatePBF(8)`、`CalculatePhi(3)`、`CalculatePmi(3)`、`CalculatePMI1(4)`、`CalculatePMI2(6)`、`CalculatePMI3(3)`、`CalculateRadiusOfGyration(9)`、`CalculateRDF(3)`、`CalculateSpherocityIndex(7)`、`CalculateTPSA(11)`、`CalculateWHIM(1)`、`CanSerialize(2)`、`CheckValidRingCut(4)`、`CreateShingling(5)`、`EncodeSECFP(2)`、`FuncGroups(2)`、`GenerateEstateFingerprint(4)`、`GenerateFraggleFragments(2)`、`GenerateMolKeyFromSmiles(4)`、`GetAliphaticCarbocyclesNum(7)`、`GetAliphaticHeterocyclesNum(7)`、`GetAliphaticRingsNum(12)`、`GetAmideBondsNum(12)`、`GetAromaticCarbocyclesNum(4)`、`GetAromaticHeterocyclesNum(7)`、`GetAromaticRingsNum(3)`、`GetAsphericity(3)`、`GetAtomFeature(1)`、`GetAtomPairFingerprint(3)`、`GetAtomPairFingerprintAsBitVect(1)`、`GetAtomsNum(6)`、`GetAtomStereoCentersNum(3)`、`GetBCUT(7)`、`GetBridgeheadAtomsNum(5)`、`GetChi0n(15)`、`GetChi0v(7)`、`GetChi1n(15)`、`GetChi1v(47)`、`GetChi2v(1)`、`GetConnectivityInvariants(5)`、`GetCoulombMat(3)`、`GetCrippenDescriptors(21)`、`GetDistanceMatrix(1)`、`GetEccentricity(6)`、`GetEEMCharges(14)`、`GetFeatureInvariants(4)`、`GetFormalCharge(2)`、`GetFormalChargeOfAtoms(3)`、`GetFractionCSP3(10)`、`GetGETAWAY(2)`、`GetHBANum(5)`、`GetHBDNum(6)`、`GetHeavyAtomsNum(10)`、`GetHeteroatomsNum(5)`、`GetHeterocyclesNum(3)`、`GetHybridization(3)`、`GetInertialShapeFactor(3)`、`GetKappa1(35)`、`GetKappa2(19)`、`GetLabuteASA(11)`、`GetLipinskiHBANum(5)`、`GetLipinskiHBDNum(5)`、`GetMACCSKeysFingerprint(4)`、`GetMolFrags(3)`、`GetMORSE(8)`、`GetNPR1(9)`、`GetNPR2(8)`、`GetRdkFingerprintFromSmiles(2)`、`GetRingsNum(6)`、`GetRingSystems(2)`、`GetRotatableBondsNum(8)`、`GetSaturatedCarbocyclesNum(4)`、`GetSaturatedHeterocyclesNum(2)`、`GetSaturatedRingsNum(5)`、`GetSpiroAtomsNum(5)`、`GetStereoCodeFromSmiles(4)`、`GetTemplateMolecule(1)`、`GetTopologicalTorsionFingerprint(2)`、`GetUnspecifiedAtomStereoCentersNum(3)`、`GetUSR(4)`、`GetUSRCAT(4)`、`Kekulize(1)`、`MolSimilarity(2)`、`MurckoDecompose(1)`、`ProcessFingerprintMol(2)`、`RemoveHydrogens(1)`、`RemoveStereochemistry(1)`、`SmallMoleculeSimilarityCalculation(2)`、`TestMolecule(2)`、`TypeAtomsInMolecule(3)`

### 标识/格式转换与查询

`ConvertingPeptide2SMILES(6)`、`GetExactMolceularWeight(11)`、`GetInchiByMoleculeId(1)`、`GetMoleculeIdByFormula(1)`、`GetMolFormula(17)`、`GetTotalEnthalpyByMoleculeId(1)`、`GetTranslationalEnthalpyByMoleculeId(1)`、`InChIKeyToSMILES(101)`、`InChIToCSID(2)`、`InChIToInChIKey(2)`、`InChIToSMILES(12)`、`LengthSELFIES(2)`、`NameToSMILES(154)`、`SELFIEStoSMILES(50)`、`SlnToSmiles(72)`、`SMILESToCAS(18)`、`SMILESToInChI(9)`、`SMILEStoSELFIES(8)`、`SMILESToWeight(2)`

### 安全与外部属性查询

`CASToPrice(1)`、`CheckExplosiveness(6)`、`SafetySummary(12)`

### 蛋白/DNA 序列工具

`AnalyzeProteinSeqFromPDB(1)`、`CalculateEnergyFromSequence(1)`、`CalculateForceFromSequence(1)`、`ComputeExtinctionCoefficient(1)`、`DoubleSequenceGlobalAlignment(1)`、`DoubleSequenceLocalAlignment(1)`、`GenerateSequenceFromEnergy(1)`、`GetElectronicEnergyByMoelculeId(1)`、`GetZeroPointEnergyByMoleculeId(1)`、`ProteinMotifAnalysis(1)`、`RandomDNAGeneration(1)`、`TranslateDNAtoAminoAcidSequence(1)`

### 材料数据库查询

`GetBandGapByFormula(1)`、`GetBandGapByMaterialId(1)`、`GetBatteryFormulaByBatteryId(1)`、`GetCrystalSystemByMaterialId(1)`、`GetDensityAtomicByMaterialId(1)`、`GetDensityByMaterialId(1)`、`GetEnergyAboveHullByMaterialId(1)`、`GetNelementsByBatteryId(1)`、`IsMetalByFormula(1)`、`IsStableByFormula(1)`、`IsStableByMaterialId(1)`

### 其他需核对原工具实现

`CustomPropertyVSA(5)`、`GetAdjacencyMatrix(2)`、`GetAutocorrelation2D(3)`、`GetAutocorrelation3D(6)`、`GetFrtool_pathCSP3(4)`、`GetHallKierAlpha(7)`
