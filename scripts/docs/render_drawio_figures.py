from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "asserts" / "figures"

FONT = "fontFamily=Helvetica;fontSize=13;"
TITLE = "fontFamily=Helvetica;fontSize=22;fontStyle=1;align=center;verticalAlign=middle;whiteSpace=wrap;html=1;"
SUBTITLE = "fontFamily=Helvetica;fontSize=12;fontColor=#475569;align=center;verticalAlign=middle;whiteSpace=wrap;html=1;"
EDGE = "endArrow=block;html=1;rounded=1;strokeWidth=2;fontSize=12;fontFamily=Helvetica;labelBackgroundColor=none;"
EDGE_DASHED = EDGE + "dashed=1;"


@dataclass(frozen=True)
class Node:
    """draw.io 节点句柄。

    Args:
        id: XML cell id。
        x: 左上角 x 坐标。
        y: 左上角 y 坐标。
        w: 节点宽度。
        h: 节点高度。
    """

    id: str
    x: int
    y: int
    w: int
    h: int


class Diagram:
    """draw.io XML 图构建器。"""

    def __init__(self, name: str, width: int, height: int) -> None:
        """初始化图模型。

        Args:
            name: diagram 标签名称。
            width: 画布宽度。
            height: 画布高度。
        """

        self.name = name
        self.width = width
        self.height = height
        self.next_id = 2
        self.model = ET.Element(
            "mxGraphModel",
            {
                "dx": str(width),
                "dy": str(height),
                "grid": "1",
                "gridSize": "10",
                "guides": "1",
                "tooltips": "1",
                "connect": "1",
                "arrows": "1",
                "fold": "1",
                "page": "1",
                "pageScale": "1",
                "pageWidth": str(width),
                "pageHeight": str(height),
                "math": "0",
                "shadow": "0",
            },
        )
        self.root = ET.SubElement(self.model, "root")
        ET.SubElement(self.root, "mxCell", {"id": "0"})
        ET.SubElement(self.root, "mxCell", {"id": "1", "parent": "0"})

    def _id(self, prefix: str) -> str:
        value = f"{prefix}{self.next_id}"
        self.next_id += 1
        return value

    def node(
        self,
        label: str,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        style: str,
        prefix: str = "n",
    ) -> Node:
        """添加普通节点。"""

        node_id = self._id(prefix)
        cell = ET.SubElement(
            self.root,
            "mxCell",
            {"id": node_id, "value": label, "style": style, "vertex": "1", "parent": "1"},
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"},
        )
        return Node(node_id, x, y, w, h)

    def edge(
        self,
        source: Node,
        target: Node,
        label: str = "",
        *,
        style: str = EDGE,
        prefix: str = "e",
        points: list[tuple[int, int]] | None = None,
    ) -> None:
        """添加节点连线。"""

        edge_id = self._id(prefix)
        cell = ET.SubElement(
            self.root,
            "mxCell",
            {
                "id": edge_id,
                "value": label,
                "style": style,
                "edge": "1",
                "parent": "1",
                "source": source.id,
                "target": target.id,
            },
        )
        geometry = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        if points:
            point_array = ET.SubElement(geometry, "Array", {"as": "points"})
            for x, y in points:
                ET.SubElement(point_array, "mxPoint", {"x": str(x), "y": str(y)})

    def save(self, path: Path) -> None:
        """保存为未压缩 draw.io 文件。"""

        mxfile = ET.Element(
            "mxfile",
            {
                "host": "app.diagrams.net",
                "modified": "2026-05-07T00:00:00.000Z",
                "agent": "Codex",
                "version": "26.0.0",
                "type": "device",
            },
        )
        diagram = ET.SubElement(mxfile, "diagram", {"name": self.name, "id": self.name.lower().replace(" ", "-")})
        diagram.append(self.model)
        tree = ET.ElementTree(mxfile)
        ET.indent(tree, space="  ")
        path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(path, encoding="utf-8", xml_declaration=True)


def box_style(fill: str, stroke: str = "#334155", *, font_size: int = 13) -> str:
    """创建圆角矩形节点样式。"""

    return (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=8;"
        f"fillColor={fill};strokeColor={stroke};strokeWidth=1.4;"
        f"fontFamily=Helvetica;fontSize={font_size};align=center;verticalAlign=middle;spacing=8;"
    )


def lane_style(fill: str) -> str:
    """创建泳道背景样式。"""

    return f"rounded=0;whiteSpace=wrap;html=1;fillColor={fill};strokeColor=#CBD5E1;strokeWidth=1;"


def note_style(fill: str = "#F8FAFC") -> str:
    """创建注释节点样式。"""

    return (
        "shape=note;whiteSpace=wrap;html=1;size=16;"
        f"fillColor={fill};strokeColor=#94A3B8;{FONT}"
        "fontSize=12;fontColor=#475569;align=left;verticalAlign=top;spacing=10;"
    )


def diamond_style(fill: str, stroke: str) -> str:
    """创建判断节点样式。"""

    return f"rhombus;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=1.4;{FONT}"


def header(d: Diagram, title: str, subtitle: str, width: int) -> None:
    """添加图标题。"""

    d.node(title, 40, 24, width - 80, 34, style=TITLE, prefix="title")
    d.node(subtitle, 70, 62, width - 140, 32, style=SUBTITLE, prefix="subtitle")


def footer(d: Diagram, text: str, width: int, height: int) -> None:
    """添加来源脚注。"""

    d.node(text, 40, height - 50, width - 80, 30, style="text;html=1;strokeColor=none;fillColor=none;fontSize=11;fontColor=#64748B;align=right;", prefix="foot")


def render_system_architecture() -> None:
    """渲染系统架构图。"""

    d = Diagram("System Architecture", 1800, 1200)
    header(
        d,
        "系统架构图：LLM 驱动的蛋白质设计多智能体工作流系统",
        "五层架构与控制面分离：输入/规划/执行/安全汇总/资源层由 Workflow FSM 与 HITL 审计链统一约束。",
        1800,
    )

    layer_x, layer_w = 80, 1640
    layers = [
        ("输入与交互层", "User / CLI / FastAPI / React Workbench<br>Task Builder, Dashboard, Pending Review, Timeline", 130, "#DBEAFE", "#2563EB"),
        ("契约与状态控制层", "ProteinDesignTask / ConfirmedTaskSpec / TaskRecord<br>WorkflowContext + ExternalStatus/InternalStatus + DecisionApply", 270, "#EDE9FE", "#7C3AED"),
        ("智能规划层", "PlannerAgent + CandidateGenerator + ProteinToolKG<br>Top-K Plan/Patch/Replan, feasibility filter, score breakdown, default recommendation", 430, "#FEF3C7", "#D97706"),
        ("执行与恢复层", "ExecutorAgent / PlanRunner / PatchRunner / StepRunner<br>PlanStep dispatch, dependency resolution, bounded retry, patch_local, suffix_replan", 610, "#DCFCE7", "#15803D"),
        ("安全、汇总与资源层", "SafetyAgent + SummarizerAgent + AdapterRegistry<br>ToolAdapters, local/remote engines, EventLog, TaskSnapshot, output artifacts", 800, "#F1F5F9", "#475569"),
    ]
    layer_nodes: list[Node] = []
    for title, body, y, fill, stroke in layers:
        d.node(title, layer_x, y, 210, 110, style=box_style(fill, stroke, font_size=15), prefix="layer")
        layer_nodes.append(d.node(body, layer_x + 250, y, layer_w - 250, 110, style=box_style(fill, stroke), prefix="layerbody"))

    d.edge(layer_nodes[0], layer_nodes[1], "normalize task / submit Decision")
    d.edge(layer_nodes[1], layer_nodes[2], "planning / recovery request", points=[(670, 380), (670, 410)])
    d.edge(
        layer_nodes[2],
        layer_nodes[1],
        "CandidateSet + PendingAction payload",
        style=EDGE_DASHED,
        points=[(520, 550), (520, 350)],
    )
    d.edge(
        layer_nodes[1],
        layer_nodes[3],
        "confirmed Plan / resume from Snapshot",
        points=[(1130, 380), (1130, 580)],
    )
    d.edge(layer_nodes[3], layer_nodes[4], "StepResult, SafetyResult, DesignResult")

    control = d.node(
        "控制面 SSOT<br>Workflow / FSM owns state mutation<br>WAITING_* pauses execution<br>retry → patch → replan",
        1280,
        300,
        340,
        150,
        style=box_style("#FFFFFF", "#7C3AED", font_size=14),
    )
    audit = d.node(
        "可恢复审计链<br>PendingAction → Decision<br>EventLog → TaskSnapshot<br>artifacts/runtime_state",
        1280,
        520,
        340,
        150,
        style=box_style("#FFFFFF", "#475569", font_size=14),
    )
    d.edge(control, audit, "write before WAITING_*", points=[(1450, 480), (1450, 500)])
    d.edge(audit, control, "recover / replay", style=EDGE_DASHED, points=[(1625, 595), (1660, 595), (1660, 375), (1625, 375)])

    tools = [
        ("Sequence generation<br>ProtGPT2 / ProteinMPNN", 240),
        ("Structure projection<br>ESMFold / NIM / OpenFold", 520),
        ("Quality gate<br>BioPython QC / DSSP", 800),
        ("Objective scoring<br>objective_ranker / metrics", 1080),
        ("Visualization/report<br>Mol* / NGL / HTML", 1360),
    ]
    for label, x in tools:
        d.node(label, x, 1010, 230, 70, style=box_style("#ECFEFF", "#0891B2", font_size=12), prefix="tool")
    d.node(
        "Resource layer details: ProteinToolKG stores capability, I/O schema, cost, safety, compatibility; AdapterRegistry maps tool_id to executable backend.",
        220,
        1100,
        1360,
        40,
        style=note_style("#F8FAFC"),
    )
    footer(
        d,
        "Sources: architecture.md (arch.overview.layers, arch.components.overview, arch.execution.nextflow_boundary), system-implementation-design.md, README.md",
        1800,
        1200,
    )
    d.save(OUT_DIR / "system-architecture.drawio")


def render_flowchart() -> None:
    """渲染 de novo 工作流与恢复控制流程图。"""

    d = Diagram("Workflow Flowchart", 1800, 1300)
    header(
        d,
        "流程图：de novo 六阶段工作流与恢复感知控制",
        "六阶段是能力分层而非固定流水线；Quality Gate、Safety Gate 与 Patch/Replan 控制层可在高代价步骤前后介入。",
        1800,
    )

    start = d.node("任务输入<br>goal + constraints", 760, 130, 240, 70, style=box_style("#DBEAFE", "#2563EB"))
    intake = d.node("Task Intake<br>字段注册表 / schema validation<br>ConfirmedTaskSpec → ProteinDesignTask", 690, 240, 380, 90, style=box_style("#E0F2FE", "#0284C7"))
    plan = d.node("Planner + ToolKG<br>生成 Top-K 候选链<br>Feasibility / cost / risk ranking", 690, 380, 380, 100, style=box_style("#FEF3C7", "#D97706"))
    gate = d.node("需要人工确认?", 745, 535, 270, 90, style=diamond_style("#FFF7ED", "#F97316"))
    wait_plan = d.node("WAITING_PLAN_CONFIRM<br>PendingAction(plan_confirm)<br>Snapshot persisted", 250, 520, 340, 110, style=box_style("#FFE4E6", "#E11D48"))

    s1 = d.node("1. 序列探索<br>Sequence Exploration<br>ProtGPT2 / candidates", 150, 730, 260, 90, style=box_style("#DBEAFE", "#2563EB"))
    s2 = d.node("2. 结构映射<br>Structure Projection<br>ESMFold / OpenFold / pLDDT", 470, 730, 260, 90, style=box_style("#E0F2FE", "#0284C7"))
    s3 = d.node("3. 质量门禁<br>Quality Gate<br>QC flags / hard feasibility", 790, 730, 260, 90, style=box_style("#F0FDFA", "#0F766E"))
    s4 = d.node("4. 结构条件精修<br>Structure-conditioned Refinement<br>ProteinMPNN / redesign", 1110, 730, 260, 90, style=box_style("#DCFCE7", "#15803D"))
    s5 = d.node("5. 目标打分<br>Objective Scoring<br>posterior objective / Top-K", 1430, 730, 260, 90, style=box_style("#FEF3C7", "#D97706"))
    summarize = d.node("结果汇总<br>DesignResult + report<br>sequence / structure / metrics", 760, 1050, 300, 90, style=box_style("#EDE9FE", "#7C3AED"))
    done = d.node("DONE", 805, 1180, 210, 55, style=box_style("#DCFCE7", "#15803D", font_size=16))
    failed = d.node("FAILED / CANCELLED", 1235, 1180, 250, 55, style=box_style("#FEE2E2", "#DC2626", font_size=15))

    safety = d.node("Safety Gate<br>input / step / output<br>allow / warn / block", 620, 890, 260, 90, style=box_style("#FFE4E6", "#E11D48"))
    control = d.node("6. Patch/Replan 控制层<br>retry exhausted / safety block / low evidence<br>patch_local / suffix_replan / stop", 1020, 890, 400, 100, style=box_style("#FFEDD5", "#F97316"))
    wait_recover = d.node("WAITING_PATCH_CONFIRM<br>或 WAITING_REPLAN_CONFIRM<br>Decision required", 1450, 910, 300, 90, style=box_style("#FEE2E2", "#DC2626"))

    for src, dst, label in [
        (start, intake, ""),
        (intake, plan, ""),
        (plan, gate, ""),
        (gate, wait_plan, "yes"),
        (wait_plan, s1, "Decision: accept"),
        (gate, s1, "no / auto allowed"),
        (s1, s2, "sequence"),
        (s2, s3, "pdb_path + confidence"),
        (s3, s4, "pass / refine"),
        (s4, s2, "iterate structure loop"),
        (s3, s5, "pass"),
        (s5, summarize, "objective accepted"),
        (summarize, done, ""),
        (s3, s1, "fail: regenerate"),
        (s5, s4, "score insufficient"),
        (s1, safety, "risk signals"),
        (s2, safety, "structure signals"),
        (s3, safety, "QC signals"),
        (s4, safety, "refinement signals"),
        (safety, control, "warn/block"),
        (control, wait_recover, "requires HITL"),
        (wait_recover, s1, "replan to earlier stage"),
        (wait_recover, s2, "patch current suffix"),
        (wait_recover, failed, "terminal stop",),
    ]:
        style = EDGE_DASHED if "signals" in label or "iterate" in label or "replan" in label else EDGE
        points: list[tuple[int, int]] | None = None
        if label == "iterate structure loop":
            points = [(1240, 690), (600, 690)]
        elif label == "fail: regenerate":
            points = [(920, 690), (280, 690)]
        elif label == "score insufficient":
            points = [(1560, 690), (1240, 690)]
        elif label == "replan to earlier stage":
            points = [(1600, 1020), (280, 1020)]
        elif label == "patch current suffix":
            points = [(1600, 1000), (600, 1000)]
        elif label == "terminal stop":
            points = [(1600, 1110), (1360, 1110)]
        d.edge(src, dst, label, style=style, points=points)

    d.node(
        "高代价控制点：结构映射、结构精修、重型目标打分之前，应检查 evidence_sufficiency、expected_remaining_cost、recovery_margin、p_structural_failure。",
        190,
        645,
        1420,
        45,
        style=note_style("#F8FAFC"),
    )
    footer(
        d,
        "Sources: de-novo-workflow.md (workflow.layers.six_stage, workflow.stage.high_cost_control, workflow.loops.and_crosscut), core-algorithm-spec.md",
        1800,
        1300,
    )
    d.save(OUT_DIR / "workflow-flowchart.drawio")


def render_uml() -> None:
    """渲染 UML 类/契约图。"""

    d = Diagram("UML Contracts", 1900, 1260)
    header(
        d,
        "UML：核心数据契约、状态枚举与 Agent 责任边界",
        "以 Pydantic/设计契约为中心展示 Plan、Candidate、PendingAction、Decision、Snapshot、RuntimeState 与四类 Agent 的关系。",
        1900,
    )

    class_style = (
        "swimlane;whiteSpace=wrap;html=1;rounded=1;startSize=34;horizontal=1;"
        "fillColor=#F8FAFC;strokeColor=#334155;strokeWidth=1.4;"
        "fontFamily=Helvetica;fontSize=12;align=center;verticalAlign=top;spacing=8;"
    )

    def cls(name: str, attrs: list[str], x: int, y: int, w: int, h: int, fill: str = "#F8FAFC") -> Node:
        body = name + "<br><br>" + "<br>".join(attrs)
        return d.node(body, x, y, w, h, style=class_style + f"fillColor={fill};", prefix="cls")

    task = cls("ProteinDesignTask", ["task_id: str", "goal: str", "constraints: dict", "metadata: dict"], 60, 150, 270, 170, "#DBEAFE")
    plan = cls("Plan", ["task_id: str", "steps: list[PlanStep]", "constraints: dict", "metadata: dict", "explanation: str | None"], 390, 150, 280, 190, "#FEF3C7")
    step = cls("PlanStep", ["id: str", "tool: str", "inputs: JsonMap", "metadata: JsonMap", "supports Sx.key refs"], 720, 150, 260, 185, "#FEF3C7")
    result = cls("StepResult", ["task_id: str", "step_id: str", "tool/tool_id/adapter_id", "status: success|failed|skipped", "outputs / metrics / artifacts", "risk_flags", "failure_type / error_details"], 1030, 140, 320, 230, "#DCFCE7")
    safety = cls("SafetyResult", ["phase: input|step|output", "scope: task|step|result", "risk_flags: list[RiskFlag]", "action: allow|warn|block"], 1410, 150, 300, 190, "#FFE4E6")

    candidate = cls("PendingActionCandidate", ["candidate_id", "summary", "structured_payload: Plan|PlanPatch", "score_breakdown", "risk_level / cost_estimate", "runtime metadata / source_refs"], 70, 460, 320, 230, "#FFF7ED")
    patch = cls("PlanPatch", ["task_id: str", "operations: list[PlanPatchOp]", "metadata: dict", "minimal local change"], 450, 470, 300, 200, "#FFEDD5")
    pending = cls("PendingAction", ["id / task_id", "action_type: plan|patch|replan", "status: pending|decided|cancelled", "candidates: list", "default_suggestion", "explanation"], 810, 450, 330, 240, "#FFE4E6")
    decision = cls("Decision", ["pending_action_id", "choice: accept|replan|continue|cancel", "selected_candidate_id", "decided_by", "comment / decided_at"], 1210, 465, 310, 210, "#DBEAFE")
    snapshot = cls("TaskSnapshot", ["task_id / state", "plan_version", "current_step_index", "completed_step_ids", "artifacts.runtime_state", "pending_action_id"], 1580, 455, 300, 225, "#E2E8F0")

    context = cls("WorkflowContext", ["task", "plan", "step_results", "safety_events", "runtime_state", "pending_action", "status: InternalStatus"], 210, 810, 350, 235, "#EDE9FE")
    runtime = cls("RuntimeState", ["p_success", "p_structural_failure", "recovery_margin", "expected_remaining_cost", "evidence_sufficiency", "last_update_source"], 650, 815, 330, 220, "#E0F2FE")
    status = cls("Status Enums", ["ExternalStatus: CREATED...DONE", "InternalStatus adds WAITING_PATCH/PATCHING", "to_external_status()", "terminal states immutable"], 1080, 815, 330, 220, "#F1F5F9")
    design = cls("DesignResult", ["task_id", "sequence | structure_pdb_path", "scores", "risk_flags", "report_path", "metadata"], 1490, 820, 310, 210, "#DCFCE7")

    for src, dst, label in [
        (task, context, "1"),
        (plan, step, "contains *"),
        (plan, context, "current"),
        (result, context, "step_results"),
        (safety, context, "safety_events"),
        (candidate, pending, "options"),
        (plan, candidate, "payload"),
        (patch, candidate, "payload"),
        (decision, pending, "resolves"),
        (pending, snapshot, "persisted before wait"),
        (runtime, context, "single work copy"),
        (context, snapshot, "minimum recovery context"),
        (context, status, "owns internal status"),
        (context, design, "summarized into"),
    ]:
        d.edge(src, dst, label, style=EDGE_DASHED if label in {"payload", "persisted before wait"} else EDGE)

    agents = [
        ("PlannerAgent<br>Plan/Patch/Replan candidates only<br>no tool execution, no state mutation", 80, "#FEF3C7", "#D97706"),
        ("ExecutorAgent<br>only tool executor<br>bounded retry, patch trigger, stop in WAITING_*", 510, "#DCFCE7", "#15803D"),
        ("SafetyAgent<br>evaluation only<br>ok / warn / block, no plan mutation", 980, "#FFE4E6", "#E11D48"),
        ("SummarizerAgent<br>only after SUMMARIZING<br>report and display artifacts", 1400, "#E0F2FE", "#0284C7"),
    ]
    for label, x, fill, stroke in agents:
        d.node(label, x, 1100, 390, 75, style=box_style(fill, stroke), prefix="agent")

    footer(
        d,
        "Sources: agent-design.md (contracts and responsibilities), system-implementation-design.md (PendingAction/Decision/TaskSnapshot/RuntimeState), src/models/*.py",
        1900,
        1260,
    )
    d.save(OUT_DIR / "uml-contracts.drawio")


def render_sequence() -> None:
    """渲染端到端时序图。"""

    d = Diagram("Runtime Sequence", 2000, 1420)
    header(
        d,
        "时序图：端到端规划、执行、HITL 与恢复闭环",
        "从任务提交、Top-K 规划、计划确认、单步执行、安全检查、patch/replan 到最终汇总的消息序列。",
        2000,
    )
    participants: Mapping[str, tuple[str, int]] = {
        "U": ("Researcher", 90),
        "API": ("TaskAPI / UI", 270),
        "WF": ("Workflow FSM", 470),
        "P": ("PlannerAgent", 670),
        "KG": ("ToolKG / LLM", 870),
        "EX": ("ExecutorAgent", 1070),
        "ST": ("StepRunner", 1270),
        "AD": ("ToolAdapter", 1470),
        "S": ("SafetyAgent", 1650),
        "DS": ("EventLog / Snapshot", 1850),
    }
    for _, (label, x) in participants.items():
        d.node(label, x - 70, 135, 140, 48, style=box_style("#F8FAFC"), prefix="p")
        d.node("", x - 1, 205, 2, 1080, style="shape=line;strokeColor=#CBD5E1;strokeWidth=1;html=1;", prefix="life")
        d.node(label, x - 70, 1305, 140, 42, style=box_style("#F8FAFC"), prefix="p")

    def point(key: str, y: int) -> Node:
        return d.node("", participants[key][1], y, 1, 1, style="shape=ellipse;fillColor=none;strokeColor=none;", prefix="m")

    def msg(src: str, dst: str, y: int, label: str, dashed: bool = False) -> None:
        d.edge(point(src, y), point(dst, y), label, style=EDGE_DASHED if dashed else EDGE)

    msg("U", "API", 240, "POST /tasks(goal, constraints)")
    msg("API", "WF", 310, "create ProteinDesignTask + TaskRecord(CREATED)")
    msg("WF", "P", 380, "plan_with_status(task, context, record)")
    msg("P", "KG", 450, "query capabilities, I/O schema, cost, safety")
    msg("KG", "P", 520, "tool candidates + provider route", True)
    msg("P", "WF", 590, "Top-K PlanCandidates + default")
    msg("WF", "DS", 660, "PENDING_ACTION_CREATED + TaskSnapshot(plan_confirm)")
    msg("WF", "API", 730, "status = WAITING_PLAN_CONFIRM", True)
    msg("U", "API", 800, "POST /pending-actions/{id}/decision")
    msg("API", "WF", 870, "validate Decision + apply_plan_confirm_decision")
    msg("WF", "DS", 940, "DECISION_APPLIED + WAITING_EXIT")
    msg("WF", "EX", 1010, "run confirmed Plan")
    msg("EX", "ST", 1080, "run_step_with_patch(step_k)")
    msg("ST", "S", 1150, "pre-step / post-step safety")
    msg("ST", "AD", 1220, "resolve inputs + run tool")
    msg("AD", "ST", 1290, "outputs / metrics / error", True)

    d.node(
        "loop for each PlanStep<br>success: STEP_FINISHED → runtime_state update → next step<br>tool failure: retry; retry exhausted → patch_top_k<br>safety block: replan_top_k<br>WAITING_*: no further tool calls until Decision",
        360,
        1110,
        700,
        125,
        style=note_style("#F8FAFC"),
    )
    d.node(
        "alt recovery branch<br>Executor → Planner: patch_top_k / replan_top_k<br>Planner → Executor/Workflow: Patch/Replan candidates<br>Workflow persists PendingAction + Snapshot before WAITING_PATCH_CONFIRM / WAITING_REPLAN_CONFIRM",
        1120,
        620,
        700,
        120,
        style=note_style("#FFF7ED"),
    )
    msg("EX", "P", 760, "patch_top_k / replan_top_k")
    msg("P", "EX", 830, "PatchCandidate / ReplanCandidate", True)
    msg("EX", "DS", 900, "WAITING_ENTER + snapshot before decision")
    msg("API", "WF", 970, "apply_patch/replan Decision")
    msg("WF", "EX", 1040, "PATCHING / REPLANNING / RUNNING", True)
    msg("EX", "DS", 1360, "final execution summary")
    msg("EX", "API", 1390, "DesignResult + report_path", True)

    footer(
        d,
        "Sources: diagrams/total-sequence.mmd, diagrams/single-step-sequence.mmd, architecture.md arch.flow.end_to_end, workflow/decision_apply.py",
        2000,
        1420,
    )
    d.save(OUT_DIR / "runtime-sequence.drawio")


def render_swimlane() -> None:
    """渲染泳道图。"""

    d = Diagram("Workflow Swimlane", 2000, 1360)
    header(
        d,
        "泳道图：生命周期阶段与组件职责边界",
        "横向是任务阶段，纵向是责任主体；每个 WAITING_* 点都先生成 PendingAction/TaskSnapshot，再由 Human Decision 驱动恢复。",
        2000,
    )
    left, top = 230, 150
    col_w = [220, 250, 280, 260, 310, 230, 260]
    cols = ["Intake", "Plan", "Plan Gate", "Execute", "Patch / Replan", "Summarize", "Audit"]
    lanes = [
        ("Human / UI", "#EFF6FF"),
        ("TaskAPI", "#F8FAFC"),
        ("Workflow / FSM", "#F5F3FF"),
        ("PlannerAgent", "#FFFBEB"),
        ("Executor / Tools", "#F0FDF4"),
        ("SafetyAgent", "#FFF1F2"),
        ("Storage / Log", "#F1F5F9"),
    ]
    x = left
    for idx, col in enumerate(cols):
        d.node(col, x, top - 56, col_w[idx], 46, style=box_style("#FFFFFF", "#94A3B8", font_size=12), prefix="col")
        x += col_w[idx]

    for row, (lane, fill) in enumerate(lanes):
        y = top + row * 140
        d.node(lane, 40, y, 170, 118, style=box_style(fill, "#94A3B8", font_size=12), prefix="lane")
        d.node("", left, y, sum(col_w), 118, style=lane_style(fill), prefix="band")

    def act(col: int, row: int, label: str, w: int = 185, fill: str = "#FFFFFF", stroke: str = "#334155") -> Node:
        x0 = left + sum(col_w[:col]) + 18
        y0 = top + row * 140 + 30
        return d.node(label, x0, y0, w, 62, style=box_style(fill, stroke, font_size=12), prefix="act")

    a1 = act(0, 0, "submit goal / constraints", 185, "#DBEAFE", "#2563EB")
    a2 = act(0, 1, "POST /tasks<br>schema validation", 185, "#DBEAFE", "#2563EB")
    a3 = act(0, 2, "CREATED<br>TaskRecord", 185, "#EDE9FE", "#7C3AED")
    a4 = act(1, 2, "PLANNING", 185, "#EDE9FE", "#7C3AED")
    a5 = act(1, 3, "Top-K candidates<br>default suggestion", 210, "#FEF3C7", "#D97706")
    a6 = act(2, 2, "WAITING_PLAN_CONFIRM<br>or PLANNED", 230, "#FFE4E6", "#E11D48")
    a7 = act(2, 6, "snapshot before wait<br>EventLog", 210, "#E2E8F0", "#475569")
    a8 = act(2, 0, "review Plan<br>Decision", 185, "#DBEAFE", "#2563EB")
    a9 = act(3, 2, "RUNNING", 180, "#EDE9FE", "#7C3AED")
    a10 = act(3, 4, "run PlanStep<br>AdapterRegistry", 210, "#DCFCE7", "#15803D")
    a11 = act(3, 5, "pre/post check<br>allow/warn/block", 210, "#FFE4E6", "#E11D48")
    a12 = act(4, 4, "retry exhausted<br>stop tool execution", 230, "#DCFCE7", "#15803D")
    a13 = act(4, 3, "Patch/Replan<br>candidate set", 230, "#FEF3C7", "#D97706")
    a14 = act(4, 2, "WAITING_PATCH_CONFIRM<br>WAITING_REPLAN_CONFIRM", 260, "#FFE4E6", "#E11D48")
    a15 = act(4, 0, "approve / replan<br>cancel / continue", 220, "#DBEAFE", "#2563EB")
    a16 = act(5, 2, "SUMMARIZING", 180, "#EDE9FE", "#7C3AED")
    a17 = act(5, 5, "final output check", 190, "#FFE4E6", "#E11D48")
    a18 = act(5, 4, "SummarizerAgent<br>DesignResult", 205, "#E0F2FE", "#0284C7")
    a19 = act(6, 6, "EventLog<br>TaskSnapshot<br>reports/artifacts", 225, "#E2E8F0", "#475569")
    a20 = act(6, 0, "view report<br>timeline", 185, "#DBEAFE", "#2563EB")

    for src, dst, label in [
        (a1, a2, ""),
        (a2, a3, ""),
        (a3, a4, "transition"),
        (a4, a5, "request"),
        (a5, a6, "CandidateSet"),
        (a6, a7, "persist"),
        (a7, a8, "expose PendingAction"),
        (a8, a9, "Decision accepted"),
        (a9, a10, "dispatch"),
        (a10, a11, "safety hooks"),
        (a11, a12, "failure/block"),
        (a12, a13, "request options"),
        (a13, a14, "PendingAction"),
        (a14, a15, "wait"),
        (a15, a9, "resume RUNNING"),
        (a9, a16, "all steps complete"),
        (a16, a17, "final check"),
        (a17, a18, "allow/warn"),
        (a18, a19, "persist outputs"),
        (a19, a20, "read-only view"),
    ]:
        d.edge(src, dst, label, style=EDGE_DASHED if label in {"wait", "resume RUNNING", "read-only view"} else EDGE)

    d.node(
        "责任边界摘要：Human/UI 只提交目标和 Decision；TaskAPI 暴露契约；Workflow/FSM 持有状态权威；Planner 生成候选；Executor 只执行已确认步骤；Safety 只评估；Storage 负责恢复与审计。",
        300,
        1165,
        1380,
        65,
        style=note_style("#F8FAFC"),
    )
    footer(
        d,
        "Sources: AGENT_CONTRACT.md, agent-design.md HITL responsibilities, architecture.md FSM lifecycle, README workflow-swimlane.svg narrative",
        2000,
        1360,
    )
    d.save(OUT_DIR / "workflow-swimlane.drawio")


def render_technical_route() -> None:
    """渲染毕业论文技术路线图。"""

    d = Diagram("Technical Route", 1900, 1180)
    header(
        d,
        "技术路线图：从问题建模到系统实现与实验验证",
        "围绕高代价、可失败、可恢复的蛋白质设计工作流，组织研究问题、方法设计、系统实现、实验评估与论文产出。",
        1900,
    )

    phases = [
        ("1. 问题定义", "蛋白质设计任务<br>高代价长链路<br>失败与恢复需求", 80, "#DBEAFE", "#2563EB"),
        ("2. 理论建模", "候选工具链集合 Π<br>约束 C / ToolKG K<br>history h_t / observation o_t", 430, "#EDE9FE", "#7C3AED"),
        ("3. 核心算法", "Top-K 候选生成<br>硬可行性过滤<br>静态效用 + runtime rerank", 780, "#FEF3C7", "#D97706"),
        ("4. 系统实现", "Workflow FSM<br>Planner / Executor / Safety / Summarizer<br>AdapterRegistry + Storage", 1130, "#DCFCE7", "#15803D"),
        ("5. 实验验证", "纵向 A0-A6<br>横向 E0-E2<br>效果 / 成本 / 治理指标", 1480, "#F1F5F9", "#475569"),
    ]
    top_nodes: list[Node] = []
    for title, body, x, fill, stroke in phases:
        top_nodes.append(d.node(f"{title}<br><br>{body}", x, 165, 290, 155, style=box_style(fill, stroke), prefix="phase"))
    for idx in range(len(top_nodes) - 1):
        d.edge(top_nodes[idx], top_nodes[idx + 1], "", points=[(top_nodes[idx].x + 310, 242), (top_nodes[idx + 1].x - 20, 242)])

    method = d.node(
        "方法主线<br>GenerateCandidates → FeasibilityFilter → StaticUtility → BeliefUpdate → RuntimeUtility → ActionSelection",
        250,
        430,
        620,
        90,
        style=box_style("#FFFFFF", "#D97706", font_size=14),
    )
    system = d.node(
        "工程主线<br>TaskAPI → Workflow/FSM → PlanRunner/PatchRunner → ToolAdapter → EventLog/TaskSnapshot",
        1030,
        430,
        620,
        90,
        style=box_style("#FFFFFF", "#15803D", font_size=14),
    )
    d.edge(top_nodes[2], method, "algorithm contribution", points=[(925, 360), (560, 360)])
    d.edge(top_nodes[3], system, "system contribution", points=[(1275, 360), (1340, 360)])
    d.edge(method, system, "runtime-aware control policy", points=[(930, 475), (970, 475)])

    evidence = [
        ("设计依据", "architecture.md<br>agent-design.md<br>core-algorithm-spec.md", 190, "#F8FAFC"),
        ("实现依据", "src/workflow<br>src/agents<br>src/models<br>src/adapters", 570, "#F8FAFC"),
        ("实验依据", "D-main / D-recovery / D-hitl<br>A0-A6 / E0-E2<br>EventLog / Snapshot", 950, "#F8FAFC"),
        ("论文产出", "系统架构<br>算法机制<br>实验结果<br>案例分析", 1330, "#F8FAFC"),
    ]
    evidence_nodes: list[Node] = []
    for title, body, x, fill in evidence:
        evidence_nodes.append(d.node(f"{title}<br>{body}", x, 690, 300, 115, style=box_style(fill, "#94A3B8"), prefix="evidence"))
    for idx in range(len(evidence_nodes) - 1):
        d.edge(evidence_nodes[idx], evidence_nodes[idx + 1], "", style=EDGE_DASHED)

    d.node(
        "图示约束：上方展示研究路线，中央展示方法与系统两条主线，下方展示证据来源与论文落点；连线采用水平/折线路径，避免穿过文本框。",
        290,
        910,
        1320,
        60,
        style=note_style("#F8FAFC"),
    )
    footer(
        d,
        "Sources: README.md project positioning, core-algorithm-spec.md, system-implementation-design.md, experiment plan",
        1900,
        1180,
    )
    d.save(OUT_DIR / "technical-route.drawio")


def render_algorithm_loop() -> None:
    """渲染核心算法闭环图。"""

    d = Diagram("Algorithm Loop", 1900, 1200)
    header(
        d,
        "算法闭环图：恢复感知的候选生成、评估与动作选择",
        "CEBRA-WP 不执行单条 LLM 计划，而是在关键决策点维护候选集合、运行时状态与 HITL/恢复动作闭环。",
        1900,
    )

    nodes = {
        "input": d.node("形式化输入<br>g: design goal<br>C: constraints<br>K: ToolKG<br>h_t: history", 120, 170, 270, 140, style=box_style("#DBEAFE", "#2563EB")),
        "gen": d.node("GenerateCandidates<br>Π_raw,t = G(g,C,K,h_t)<br>Plan / Patch / Replan Top-K", 510, 170, 310, 140, style=box_style("#FEF3C7", "#D97706")),
        "filter": d.node("FeasibilityFilter<br>F_tool ∧ F_schema ∧ F_io<br>F_safety ∧ F_budget ∧ F_availability", 940, 170, 340, 140, style=box_style("#FFF7ED", "#F97316")),
        "static": d.node("StaticUtility<br>goal fit + feasibility<br>cost / risk / recovery complexity<br>readiness / fallback", 1420, 170, 330, 140, style=box_style("#F0FDFA", "#0F766E")),
        "observe": d.node("Runtime Observation o_t<br>StepResult.metrics<br>SafetyResult.risk_flags<br>budget and recovery history", 120, 520, 310, 140, style=box_style("#E0F2FE", "#0284C7")),
        "belief": d.node("BeliefUpdate<br>x_t = (p_success, p_structural_failure,<br>recovery_margin, expected_remaining_cost,<br>evidence_sufficiency)", 560, 520, 420, 150, style=box_style("#EDE9FE", "#7C3AED")),
        "runtime": d.node("RuntimeCandidateUtility<br>final_score = static_score + runtime_adjustment<br>hard infeasible never promoted", 1110, 520, 390, 140, style=box_style("#FEF3C7", "#D97706")),
        "action": d.node("RecoveryAwareActionSelection<br>continue / patch_local<br>suffix_replan / stop", 720, 850, 360, 120, style=box_style("#DCFCE7", "#15803D", font_size=14)),
        "hitl": d.node("HITL Gate<br>PendingAction + Decision<br>when risk/cost/uncertainty requires review", 1260, 850, 340, 120, style=box_style("#FFE4E6", "#E11D48")),
    }

    d.edge(nodes["input"], nodes["gen"], "task context")
    d.edge(nodes["gen"], nodes["filter"], "Π_raw,t")
    d.edge(nodes["filter"], nodes["static"], "Π_t")
    d.edge(nodes["static"], nodes["runtime"], "S_static(π)", points=[(1585, 390), (1305, 390)])
    d.edge(nodes["observe"], nodes["belief"], "o_t")
    d.edge(nodes["belief"], nodes["runtime"], "x_t summary")
    d.edge(nodes["runtime"], nodes["action"], "ranked candidates", points=[(1305, 750), (900, 750)])
    d.edge(nodes["action"], nodes["hitl"], "if WAITING_* needed")
    d.edge(nodes["hitl"], nodes["observe"], "Decision + new evidence", style=EDGE_DASHED, points=[(1430, 1060), (275, 1060)])
    d.edge(nodes["action"], nodes["gen"], "patch/replan request", style=EDGE_DASHED, points=[(760, 790), (665, 790), (665, 350)])

    d.node(
        "硬优先级：Safety block 禁止 continue；schema/I-O/tool availability 违规直接淘汰；retry_exhausted 且局部可修时优先 patch_local；stop 默认进入 replan_confirm 候选。",
        230,
        1030,
        1440,
        65,
        style=note_style("#F8FAFC"),
    )
    footer(
        d,
        "Sources: core-algorithm-spec.md (algo.adaptive.problem_formulation, feasibility_filter, runtime_action_selection), runtime-adaptation-formalization.md",
        1900,
        1200,
    )
    d.save(OUT_DIR / "algorithm-loop.drawio")


def render_fsm_state_transition() -> None:
    """渲染 FSM 状态转移图。"""

    d = Diagram("FSM State Transition", 1900, 1200)
    header(
        d,
        "FSM 状态转移图：外部生命周期、内部恢复态与 HITL 决策边界",
        "状态突变由 Workflow/FSM 统一负责；WAITING_* 表示执行暂停，终态不可再修改。",
        1900,
    )

    created = d.node("CREATED", 100, 220, 180, 65, style=box_style("#F8FAFC", "#475569", font_size=15))
    planning = d.node("PLANNING", 360, 220, 190, 65, style=box_style("#FEF3C7", "#D97706", font_size=15))
    wait_plan = d.node("WAITING_PLAN_CONFIRM<br>PendingAction(plan_confirm)", 670, 165, 270, 90, style=box_style("#FFE4E6", "#E11D48"))
    planned = d.node("PLANNED", 690, 325, 200, 65, style=box_style("#DCFCE7", "#15803D", font_size=15))
    running = d.node("RUNNING", 1050, 300, 210, 75, style=box_style("#DCFCE7", "#15803D", font_size=16))
    summarizing = d.node("SUMMARIZING", 1450, 220, 230, 70, style=box_style("#E0F2FE", "#0284C7", font_size=15))
    done = d.node("DONE", 1700, 220, 150, 70, style=box_style("#DCFCE7", "#15803D", font_size=16))

    wait_patch = d.node("WAITING_PATCH_CONFIRM<br>external view<br>internal: WAITING_PATCH / PATCHING", 700, 590, 330, 105, style=box_style("#FFEDD5", "#F97316"))
    wait_replan = d.node("WAITING_REPLAN_CONFIRM<br>external view<br>internal: WAITING_REPLAN / REPLANNING", 1120, 590, 350, 105, style=box_style("#FFE4E6", "#E11D48"))
    failed = d.node("FAILED<br>terminal", 510, 875, 200, 75, style=box_style("#FEE2E2", "#DC2626", font_size=15))
    cancelled = d.node("CANCELLED<br>terminal", 890, 875, 220, 75, style=box_style("#F1F5F9", "#64748B", font_size=15))

    d.edge(created, planning)
    d.edge(planning, wait_plan, "requires HITL")
    d.edge(planning, planned, "auto allowed")
    d.edge(wait_plan, planned, "Decision: accept")
    d.edge(planned, running)
    d.edge(running, summarizing, "all steps done")
    d.edge(summarizing, done)
    d.edge(running, wait_patch, "local failure", points=[(1155, 470), (865, 470)])
    d.edge(running, wait_replan, "safety block / global risk", points=[(1155, 510), (1295, 510)])
    d.edge(wait_patch, running, "Decision: apply patch", points=[(865, 760), (1155, 760)])
    d.edge(wait_patch, wait_replan, "Decision: replan")
    d.edge(wait_replan, running, "Decision: apply suffix replan", points=[(1295, 805), (1155, 805)])
    d.edge(wait_plan, failed, "reject", style=EDGE_DASHED, points=[(805, 455), (610, 455)])
    d.edge(wait_plan, cancelled, "cancel", style=EDGE_DASHED, points=[(805, 495), (1000, 495)])
    d.edge(wait_patch, cancelled, "cancel", style=EDGE_DASHED)
    d.edge(wait_replan, failed, "terminal_stop / reject", style=EDGE_DASHED)

    d.node(
        "WAITING_* invariant<br>1. Snapshot/log already persisted<br>2. no tool execution while waiting<br>3. only human Decision can resume / fail / cancel",
        1170,
        880,
        410,
        115,
        style=note_style("#F8FAFC"),
    )
    d.node(
        "ExternalStatus exposes WAITING_PATCH_CONFIRM / WAITING_REPLAN_CONFIRM; InternalStatus may use WAITING_PATCH, PATCHING, WAITING_REPLAN, REPLANNING for implementation detail.",
        220,
        1030,
        1380,
        50,
        style=note_style("#F8FAFC"),
    )
    footer(
        d,
        "Sources: AGENT_CONTRACT.md, architecture.md fsm.lifecycle.overview, src/models/db.py, src/workflow/status.py",
        1900,
        1200,
    )
    d.save(OUT_DIR / "fsm-state-transition.drawio")


def render_experiment_design_framework() -> None:
    """渲染实验设计框架图。"""

    d = Diagram("Experiment Design Framework", 1900, 1220)
    header(
        d,
        "实验设计框架图：数据集、对比组、指标与证据链",
        "实验围绕纵向机制增量、横向代理范式对照、成本与治理指标展开，所有结论追溯到日志、快照、配置与评估脚本。",
        1900,
    )

    data = d.node("实验数据集<br>D-main: 主任务集<br>D-recovery: 恢复压力集<br>D-hitl: 人工决策集", 90, 200, 310, 150, style=box_style("#DBEAFE", "#2563EB"))
    split = d.node("切分与防泄漏<br>time split<br>task_goal + constraints_hash<br>sequence_hash + tool_lineage", 90, 430, 310, 145, style=box_style("#E0F2FE", "#0284C7"))

    vertical = d.node("纵向机制增量<br>A0: degraded baseline<br>A1/A2: Top-K + hard validation<br>A3/A4: gates + recovery<br>A5/A6: six-stage + fallback + audit", 560, 170, 430, 190, style=box_style("#FEF3C7", "#D97706"))
    horizontal = d.node("横向对照<br>E0: ReAct-style<br>E1: ToT-style<br>E2: Reflexion-style<br>same tools / same budget", 560, 440, 430, 170, style=box_style("#FFF7ED", "#F97316"))

    runner = d.node("统一评估执行器<br>fixed seed / config version<br>tool whitelist / runtime policy<br>EventLog + TaskSnapshot capture", 1140, 300, 390, 170, style=box_style("#DCFCE7", "#15803D"))
    metrics = d.node("指标体系<br>效果: success / first-pass / constraints<br>机制: schema / executable / patch/replan<br>代价: latency / token / remote calls<br>治理: audit / trace / replay", 1140, 610, 390, 210, style=box_style("#EDE9FE", "#7C3AED"))
    stats = d.node("统计分析<br>Wilson 95% CI<br>paired McNemar<br>bootstrap CI<br>effect size", 1550, 610, 280, 170, style=box_style("#F1F5F9", "#475569"))
    outputs = d.node("论文图表产出<br>A0-A6 总表<br>A6 vs E0/E1/E2<br>success-latency Pareto<br>recovery path distribution<br>audit radar", 760, 920, 430, 180, style=box_style("#F8FAFC", "#334155"))

    d.edge(data, split, "quality gate")
    d.edge(split, vertical, "same input set", points=[(420, 505), (520, 265)])
    d.edge(split, horizontal, "same budget", points=[(420, 505), (520, 525)])
    d.edge(vertical, runner, "run groups")
    d.edge(horizontal, runner, "run baselines")
    d.edge(runner, metrics, "raw logs + artifacts")
    d.edge(metrics, stats, "aggregated indicators")
    d.edge(stats, outputs, "tables and figures", points=[(1690, 900), (975, 900)])
    d.edge(metrics, outputs, "metric tables", points=[(1335, 880), (975, 880)])
    d.edge(runner, outputs, "evidence index", style=EDGE_DASHED, points=[(1335, 530), (1335, 850), (975, 850)])

    d.node(
        "通过门槛示例：schema 合法率 ≥ 99.5%；可执行 Plan 率 ≥ 95%；Patch 最小性命中率 ≥ 80%；suffix_replan 前缀保持率 = 100%；治理指标不下降。",
        230,
        760,
        760,
        85,
        style=note_style("#F8FAFC"),
    )
    footer(
        d,
        "Sources: docs/experiment/w11-w12-midterm-experiment-plan.md, docs/experiment/algorithm-group-paper-mapping.md, reports and evaluation scripts",
        1900,
        1220,
    )
    d.save(OUT_DIR / "experiment-design-framework.drawio")


def main() -> None:
    """生成论文图示 draw.io 文件。"""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    render_system_architecture()
    render_flowchart()
    render_uml()
    render_sequence()
    render_swimlane()
    render_technical_route()
    render_algorithm_loop()
    render_fsm_state_transition()
    render_experiment_design_framework()


if __name__ == "__main__":
    main()
