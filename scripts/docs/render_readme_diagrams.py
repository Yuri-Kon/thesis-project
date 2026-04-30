from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "assets" / "readme"

INK = "#111111"
MUTED = "#606873"
GRAY = "#c9cdd3"
GRAY_DARK = "#7c838d"
GREEN = "#6fb23f"
GREEN_DARK = "#275f13"
PANEL = "#f7f8fa"
BLUE = "#eaf4ff"
MINT = "#eff9f1"
AMBER = "#fff5df"
LILAC = "#f5efff"
ROSE = "#fff1f1"

TEXT_STYLES = {
    "h1": (
        "font-family:Arial, Helvetica, sans-serif;font-size:34px;"
        "font-weight:800;fill:#111111"
    ),
    "h2": (
        "font-family:Arial, Helvetica, sans-serif;font-size:19px;"
        "font-weight:800;fill:#111111"
    ),
    "h3": (
        "font-family:Arial, Helvetica, sans-serif;font-size:15px;"
        "font-weight:700;fill:#111111"
    ),
    "body": (
        "font-family:Arial, Helvetica, sans-serif;font-size:14px;"
        "font-weight:400;fill:#252c35"
    ),
    "small": (
        "font-family:Arial, Helvetica, sans-serif;font-size:12.5px;"
        "font-weight:400;fill:#606873"
    ),
    "mono": (
        "font-family:Consolas, 'Liberation Mono', Menlo, monospace;font-size:14px;"
        "font-weight:500;fill:#111111"
    ),
    "mono-green": (
        "font-family:Consolas, 'Liberation Mono', Menlo, monospace;font-size:15px;"
        "font-weight:500;fill:#275f13"
    ),
    "mono-small": (
        "font-family:Consolas, 'Liberation Mono', Menlo, monospace;font-size:12px;"
        "font-weight:400;fill:#404852"
    ),
    "lane": (
        "font-family:Consolas, 'Liberation Mono', Menlo, monospace;font-size:13px;"
        "font-weight:800;fill:#111111"
    ),
    "tag": (
        "font-family:Arial, Helvetica, sans-serif;font-size:11px;"
        "font-weight:800;fill:#606873;letter-spacing:.8px"
    ),
}


@dataclass(frozen=True)
class Point:
    """二维坐标。"""

    x: int
    y: int


class Svg:
    """README 图示的 SVG 拼装器。"""

    def __init__(self, width: int, height: int, title: str, desc: str) -> None:
        """初始化 SVG 画布。

        Args:
            width: 画布宽度。
            height: 画布高度。
            title: 图标题。
            desc: 无障碍说明。
        """

        self.width = width
        self.height = height
        self.title = title
        self.desc = desc
        self.parts: list[str] = []

    def add(self, markup: str) -> None:
        """追加 SVG 片段。"""

        self.parts.append(markup)

    def render(self) -> str:
        """渲染完整 SVG。"""

        body = "\n".join(self.parts)
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(self.title)}</title>
  <desc id="desc">{escape(self.desc)}</desc>
  <defs>
    <pattern id="dots-green" width="11" height="11" patternUnits="userSpaceOnUse">
      <circle cx="2.2" cy="2.2" r="1.05" fill="#a7d486" opacity="0.72"/>
    </pattern>
    <pattern id="dots-gray" width="11" height="11" patternUnits="userSpaceOnUse">
      <circle cx="2.2" cy="2.2" r="1.0" fill="#b9bec6" opacity="0.62"/>
    </pattern>
    <pattern id="dots-blue" width="12" height="12" patternUnits="userSpaceOnUse">
      <circle cx="2.3" cy="2.3" r="1.0" fill="#8ab5e8" opacity="0.36"/>
    </pattern>
    <marker id="arrow-green" markerWidth="12" markerHeight="10" refX="10" refY="5" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L10,5 L0,10 z" fill="{GREEN}"/>
    </marker>
    <marker id="arrow-gray" markerWidth="12" markerHeight="10" refX="10" refY="5" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L10,5 L0,10 z" fill="{GRAY_DARK}"/>
    </marker>
  </defs>
  <rect x="0" y="0" width="{self.width}" height="{self.height}" fill="#ffffff"/>
{body}
</svg>
"""


def text(x: int, y: int, value: str, cls: str = "body", anchor: str = "start") -> str:
    """创建单行文本。"""

    style = TEXT_STYLES[cls]
    return f'<text x="{x}" y="{y}" style="{style}" text-anchor="{anchor}">{escape(value)}</text>'


def wrapped_text(
    x: int,
    y: int,
    value: str,
    *,
    chars: int = 28,
    cls: str = "small",
    gap: int = 17,
    anchor: str = "start",
) -> str:
    """创建自动折行文本。

    Args:
        x: 文本 x 坐标。
        y: 第一行 baseline。
        value: 文本内容。
        chars: 每行粗略字符数。
        cls: CSS 类。
        gap: 行距。
        anchor: 对齐方式。
    """

    lines = wrap(value, width=chars, break_long_words=False, break_on_hyphens=False)
    return "\n".join(text(x, y + i * gap, line, cls, anchor) for i, line in enumerate(lines))


def rect(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    fill: str = "#ffffff",
    stroke: str = INK,
    rx: int = 18,
    sw: float = 1.45,
    pattern: str | None = None,
    opacity: float = 0.45,
) -> str:
    """创建圆角矩形，可叠加点阵。"""

    overlay = ""
    if pattern:
        overlay = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="url(#{pattern})" opacity="{opacity}"/>'
    return "\n".join(
        [
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>',
            overlay,
        ]
    )


def pill(
    x: int,
    y: int,
    w: int,
    h: int,
    label: str,
    *,
    stroke: str = INK,
    fill: str = "#ffffff",
    pattern: str = "dots-gray",
    cls: str = "mono",
) -> str:
    """创建胶囊节点。"""

    return "\n".join(
        [
            rect(x, y, w, h, fill=fill, stroke=stroke, rx=h // 2, pattern=pattern, opacity=0.65),
            text(x + w // 2, y + h // 2 + 5, label, cls, "middle"),
        ]
    )


def card(
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    body: tuple[str, ...],
    *,
    fill: str,
    stroke: str = "#2d333b",
    title_cls: str = "h3",
) -> str:
    """创建信息卡片，文本位置固定以避免重叠。"""

    parts = [rect(x, y, w, h, fill=fill, stroke=stroke, rx=15, pattern="dots-blue", opacity=0.12)]
    parts.append(text(x + 18, y + 30, title, title_cls))
    for idx, line in enumerate(body):
        parts.append(text(x + 18, y + 58 + idx * 20, line, "small"))
    return "\n".join(parts)


def arrow(
    start: Point,
    end: Point,
    *,
    color: str = GREEN,
    dashed: bool = False,
    marker: str = "arrow-green",
    label: str | None = None,
    label_pos: Point | None = None,
    label_width: int = 180,
    label_cls: str = "mono-green",
    bend: Point | None = None,
) -> str:
    """创建箭头，标签使用白底以避免与线条重叠。"""

    dash = ' stroke-dasharray="7 7"' if dashed else ""
    if bend:
        path = f"M{start.x},{start.y} L{bend.x},{bend.y} L{end.x},{end.y}"
        default_label = Point(bend.x, bend.y - 12)
    else:
        path = f"M{start.x},{start.y} L{end.x},{end.y}"
        default_label = Point((start.x + end.x) // 2, (start.y + end.y) // 2 - 12)
    label_markup = ""
    if label:
        p = label_pos or default_label
        label_chars = max(10, label_width // 8)
        label_lines = wrap(label, width=label_chars, break_long_words=False, break_on_hyphens=False)
        label_h = 16 + len(label_lines) * 16
        label_y = p.y - label_h + 10
        lines = [
            f'<rect x="{p.x - label_width // 2}" y="{label_y}" width="{label_width}" height="{label_h}" rx="12" fill="#ffffff" opacity="0.96"/>'
        ]
        first_baseline = label_y + 20
        for idx, line in enumerate(label_lines):
            lines.append(text(p.x, first_baseline + idx * 16, line, label_cls, "middle"))
        label_markup = "\n".join(lines)
    return "\n".join(
        [
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.1" marker-end="url(#{marker})"{dash}/>',
            label_markup,
        ]
    )


def render_system_architecture() -> None:
    """绘制架构图。"""

    svg = Svg(
        1500,
        920,
        "架构图：LLM 驱动的蛋白质设计工作流系统",
        "依据设计文档展示输入层、智能规划层、执行层、安全汇总层、资源层与审计闭环。",
    )
    svg.add(text(52, 66, "Layered architecture: planning suggestions, controlled execution, auditable recovery", "h1"))
    svg.add(text(54, 100, "The design keeps control-flow authority in Workflow/FSM while agents stay inside their role boundaries.", "small"))

    svg.add(pill(610, 148, 300, 78, "WORKFLOW / FSM", stroke=GREEN, pattern="dots-green", cls="mono"))
    svg.add(text(760, 258, "State authority", "tag", "middle"))
    svg.add(arrow(Point(760, 226), Point(760, 308), color=GRAY_DARK, marker="arrow-gray", label=None))

    svg.add(rect(92, 308, 1316, 420, fill=PANEL, stroke=GRAY_DARK, rx=34, pattern="dots-gray", opacity=0.22))
    svg.add(text(128, 348, "Runtime kernel", "h2"))

    blocks = [
        (132, 388, 220, 128, "Interface layer", ("React workbench", "CLI / scripts", "TaskAPI"), BLUE),
        (396, 388, 220, 128, "Contract layer", ("ProteinDesignTask", "Plan / StepResult", "schema validation"), MINT),
        (660, 388, 220, 128, "Planner + KG", ("Top-K CandidateSet", "ToolKG constraints", "default suggestion"), AMBER),
        (924, 388, 220, 128, "Executor + Tools", ("PlanStep dispatch", "ToolAdapter / REST", "retry boundary"), LILAC),
        (1188, 388, 180, 128, "Safety + Summary", ("ok / warn / block", "DesignResult", "report"), ROSE),
    ]
    for x, y, w, h, title, lines, fill in blocks:
        svg.add(card(x, y, w, h, title, lines, fill=fill))

    svg.add(arrow(Point(352, 452), Point(396, 452), label=None))
    svg.add(arrow(Point(616, 452), Point(660, 452), label=None, color=GRAY_DARK, marker="arrow-gray"))
    svg.add(arrow(Point(880, 452), Point(924, 452), label=None))
    svg.add(arrow(Point(1144, 452), Point(1188, 452), label=None, color=GRAY_DARK, marker="arrow-gray"))
    svg.add(text(374, 374, "task", "tag", "middle"))
    svg.add(text(638, 374, "schema", "tag", "middle"))
    svg.add(text(902, 374, "plan", "tag", "middle"))
    svg.add(text(1166, 374, "result", "tag", "middle"))

    svg.add(card(396, 566, 220, 112, "RuntimeState", ("p_success", "p_structural_failure", "recovery_margin", "cost / evidence"), fill="#ffffff"))
    svg.add(card(660, 566, 220, 112, "HITL gate", ("PendingAction", "Decision", "WAITING_* pause"), fill="#ffffff"))
    svg.add(card(924, 566, 220, 112, "Audit store", ("TaskSnapshot", "EventLog", "artifacts / reports"), fill="#ffffff"))
    svg.add(arrow(Point(760, 516), Point(760, 566), color=GRAY_DARK, marker="arrow-gray", label="pause before decision", label_pos=Point(760, 548), label_cls="small", label_width=170))
    svg.add(arrow(Point(616, 622), Point(660, 622), color=GRAY_DARK, marker="arrow-gray", label="context", label_cls="small", label_width=100))
    svg.add(arrow(Point(880, 622), Point(924, 622), color=GRAY_DARK, marker="arrow-gray", label="write-ahead", label_cls="small", label_width=120))

    svg.add(rect(180, 780, 1140, 74, fill="#fbfff7", stroke=GREEN, rx=34, pattern="dots-green", opacity=0.36))
    svg.add(text(750, 812, "Recovery and observability rail", "h3", "middle"))
    svg.add(text(750, 838, "retry -> patch -> replan;  PendingAction -> Decision -> EventLog -> TaskSnapshot", "mono-small", "middle"))
    svg.add(arrow(Point(1204, 780), Point(880, 678), color=GREEN, marker="arrow-green", dashed=True, label="recover from latest snapshot", label_pos=Point(1120, 720), label_width=220))
    svg.add(arrow(Point(660, 780), Point(616, 678), color=GREEN, marker="arrow-green", dashed=True, label="runtime summary", label_pos=Point(610, 740), label_width=150))

    svg.add(text(134, 246, "Design source: architecture.md / system-implementation-design.md", "mono-small"))
    svg.add(text(1020, 246, "Control-flow SSOT stays in Workflow/FSM; Nextflow is only a PlanStep backend.", "mono-small"))

    (OUT_DIR / "system-architecture.svg").write_text(svg.render(), encoding="utf-8")


def render_workflow_swimlane() -> None:
    """绘制泳道图。"""

    svg = Svg(
        1500,
        980,
        "泳道图：任务生命周期与组件职责",
        "展示 API、Workflow/FSM、Planner、Executor、Safety、Storage、Human 在任务阶段中的职责边界。",
    )
    svg.add(text(52, 66, "Swimlane: task lifecycle, agent boundaries, and HITL checkpoints", "h1"))
    svg.add(text(54, 100, "Rows show ownership; columns show lifecycle stages. WAITING_* rows stop execution until a Decision arrives.", "small"))

    left = 210
    top = 160
    lane_h = 86
    cols = [
        (left, "Intake", 170),
        (left + 170, "Plan", 190),
        (left + 360, "Execute", 210),
        (left + 570, "Recover", 270),
        (left + 840, "Summarize", 180),
        (left + 1020, "Audit", 210),
    ]
    lanes = [
        ("Human / UI", "#fbfff7"),
        ("TaskAPI", "#ffffff"),
        ("Workflow / FSM", "#fbfff7"),
        ("PlannerAgent", "#ffffff"),
        ("Executor / Tools", "#ffffff"),
        ("SafetyAgent", "#ffffff"),
        ("Storage / Log", "#ffffff"),
    ]

    svg.add(rect(62, top - 54, 1376, 56, fill="#ffffff", stroke=GRAY, rx=20, pattern="dots-gray", opacity=0.18))
    for x, label, width in cols:
        svg.add(text(x + width // 2, top - 20, label.upper(), "tag", "middle"))
        svg.add(f'<path d="M{x},{top - 54} L{x},{top + lane_h * len(lanes)}" stroke="{GRAY}" stroke-width="1.2"/>')
    svg.add(f'<path d="M{left + 1230},{top - 54} L{left + 1230},{top + lane_h * len(lanes)}" stroke="{GRAY}" stroke-width="1.2"/>')

    for idx, (label, fill) in enumerate(lanes):
        y = top + idx * lane_h
        svg.add(rect(62, y, 1376, lane_h, fill=fill, stroke=GRAY, rx=0, pattern="dots-green" if idx in (0, 2) else None, opacity=0.12))
        svg.add(text(90, y + 52, label, "lane"))

    activities = [
        (224, 176, 142, 42, "submit goal", GREEN),
        (228, 262, 136, 42, "create task", GRAY_DARK),
        (422, 348, 150, 42, "CREATED -> PLANNING", GREEN),
        (424, 434, 150, 42, "Top-K candidates", GRAY_DARK),
        (610, 348, 156, 42, "WAITING_PLAN_CONFIRM", GREEN),
        (608, 176, 154, 42, "review plan", GREEN),
        (800, 348, 140, 42, "RUNNING", GREEN),
        (800, 520, 142, 42, "run PlanStep", GRAY_DARK),
        (812, 606, 120, 42, "check step", GRAY_DARK),
        (1016, 348, 176, 42, "WAITING_PATCH / REPLAN", GREEN),
        (1010, 434, 188, 42, "patch / suffix replan", GRAY_DARK),
        (1014, 176, 182, 42, "approve Decision", GREEN),
        (1218, 348, 150, 42, "SUMMARIZING", GREEN),
        (1216, 606, 154, 42, "final safety", GRAY_DARK),
        (1220, 692, 150, 42, "EventLog + Snapshot", GRAY_DARK),
    ]
    for x, y, w, h, label, stroke in activities:
        svg.add(rect(x, y, w, h, fill="#ffffff", stroke=stroke, rx=18, pattern="dots-green" if stroke == GREEN else "dots-gray", opacity=0.26))
        svg.add(text(x + w // 2, y + 26, label, "mono-small", "middle"))

    flow_points = [
        (Point(366, 197), Point(424, 455)),
        (Point(574, 455), Point(610, 369)),
        (Point(685, 348), Point(685, 218)),
        (Point(762, 197), Point(800, 369)),
        (Point(940, 369), Point(1016, 369)),
        (Point(1192, 369), Point(1218, 369)),
    ]
    for start, end in flow_points:
        svg.add(arrow(start, end, color=GREEN, marker="arrow-green", dashed=True, label=None))

    svg.add(arrow(Point(942, 542), Point(1016, 369), color=GRAY_DARK, marker="arrow-gray", label="failure or block", label_pos=Point(1030, 520), label_width=150, label_cls="small", dashed=True))
    svg.add(arrow(Point(1104, 434), Point(1104, 218), color=GREEN, marker="arrow-green", label="Decision required", label_pos=Point(1162, 318), label_width=150, label_cls="small"))
    svg.add(arrow(Point(1010, 455), Point(940, 369), color=GREEN, marker="arrow-green", dashed=True, label="resume RUNNING", label_pos=Point(968, 436), label_width=150, label_cls="small"))

    svg.add(rect(930, 790, 404, 86, fill="#fbfff7", stroke=GREEN, rx=28, pattern="dots-green", opacity=0.28))
    svg.add(text(1132, 824, "Invariant highlighted by design docs", "h3", "middle"))
    svg.add(text(1132, 850, "Planner suggests; Workflow mutates state; Executor runs tools; Human approves.", "mono-small", "middle"))

    (OUT_DIR / "workflow-swimlane.svg").write_text(svg.render(), encoding="utf-8")


def render_runtime_sequence() -> None:
    """绘制时序图。"""

    svg = Svg(
        1500,
        1120,
        "时序图：端到端执行与恢复闭环",
        "展示 User、TaskAPI、Workflow、Planner、ToolKG、Executor、ToolAdapter、Safety、Storage 之间的端到端消息。",
    )
    svg.add(text(52, 66, "Sequence: end-to-end planning, execution, and recovery loop", "h1"))
    svg.add(text(54, 100, "Labels are placed away from lifelines and arrows to avoid overlap while preserving the architecture.md flow.", "small"))

    participants = [
        (118, "USER"),
        (282, "TASK API"),
        (456, "WORKFLOW"),
        (640, "PLANNER"),
        (816, "TOOL KG"),
        (994, "EXECUTOR"),
        (1174, "TOOL ADAPTER"),
        (1340, "SAFETY / STORE"),
    ]
    for x, label in participants:
        stroke = GREEN if label in {"USER", "WORKFLOW"} else GRAY_DARK
        pattern = "dots-green" if label in {"USER", "WORKFLOW"} else "dots-gray"
        svg.add(pill(x - 72, 148, 144, 58, label, stroke=stroke, pattern=pattern, cls="mono-small"))
        svg.add(f'<path d="M{x},{206} L{x},{1036}" stroke="{GRAY}" stroke-width="1.7"/>')
        svg.add(pill(x - 72, 1042, 144, 50, label, stroke=stroke, pattern=pattern, cls="mono-small"))

    messages = [
        (246, 118, 282, "natural-language goal"),
        (300, 282, 456, "create ProteinDesignTask"),
        (354, 456, 640, "request Top-K candidates"),
        (408, 640, 816, "query ToolKG constraints"),
        (462, 816, 640, "tool schemas / cost / risk"),
        (516, 640, 456, "CandidateSet + default"),
        (570, 456, 1340, "write PendingAction or PlanSnapshot"),
        (624, 456, 994, "run confirmed Plan"),
        (678, 994, 1174, "execute PlanStep"),
        (732, 1174, 994, "StepResult"),
        (786, 994, 1340, "persist StepResult + metrics"),
        (840, 994, 1340, "pre/post safety check"),
        (894, 1340, 456, "ok / warn / block"),
        (948, 456, 640, "patch or suffix replan request"),
    ]
    for y, x1, x2, label in messages:
        color = GREEN if x2 > x1 else GRAY_DARK
        marker = "arrow-green" if color == GREEN else "arrow-gray"
        cls = "mono-green" if color == GREEN else "mono-small"
        start = Point(x1 + 18 if x2 > x1 else x1 - 18, y)
        end = Point(x2 - 18 if x2 > x1 else x2 + 18, y)
        svg.add(arrow(start, end, color=color, marker=marker, label=label, label_pos=Point((x1 + x2) // 2, y - 12), label_width=230, label_cls=cls))

    svg.add(rect(420, 876, 952, 136, fill="#fbfff7", stroke=GREEN, rx=14, pattern="dots-green", opacity=0.22))
    svg.add(rect(420, 876, 98, 36, fill="#ffffff", stroke=GREEN, rx=10))
    svg.add(text(469, 900, "LOOP", "lane", "middle"))
    svg.add(text(1084, 904, "retry -> patch -> replan", "mono-small", "middle"))
    svg.add(text(1084, 928, "until RUNNING resumes or recovery is exhausted", "mono-small", "middle"))
    svg.add(arrow(Point(640, 986), Point(456, 986), color=GREEN, marker="arrow-green", label="Decision applied returns control", label_pos=Point(548, 976), label_width=220))

    svg.add(text(86, 1010, "WAITING_* gates are persisted before the user sees the decision.", "mono-small"))
    svg.add(text(816, 1010, "Safety block maps to WAITING_REPLAN_CONFIRM, not hidden execution.", "mono-small"))

    (OUT_DIR / "runtime-sequence.svg").write_text(svg.render(), encoding="utf-8")


def render_frontend_flow() -> None:
    """绘制前端工作台图。"""

    svg = Svg(
        1500,
        820,
        "前端工作台：决策上下文同屏",
        "展示 Web workspace 如何通过正式 API 呈现任务、待办、候选、事件和报告。",
    )
    svg.add(text(52, 66, "Workbench view: API-backed task review, not a second workflow engine", "h1"))
    svg.add(text(54, 100, "The browser never mutates FSM directly; it reads server state and submits Decision requests.", "small"))

    svg.add(rect(112, 174, 1276, 270, fill=PANEL, stroke=GRAY_DARK, rx=42, pattern="dots-gray", opacity=0.2))
    views = [
        (158, "Task Builder", "field registry / extraction / precheck"),
        (412, "Dashboard", "task scan / pending entry / readiness"),
        (666, "Task Detail", "status / artifacts / runtime summary"),
        (920, "Pending Review", "candidate comparison / DecisionForm"),
        (1174, "Timeline", "EventLog / recovery trace / reports"),
    ]
    for x, title, body in views:
        svg.add(card(x, 238, 198, 120, title, tuple(wrap(body, width=25)), fill="#ffffff"))
    for x1, x2, label in [(356, 412, "open"), (610, 666, "inspect"), (864, 920, "decide"), (1118, 1174, "audit")]:
        svg.add(arrow(Point(x1, 298), Point(x2, 298), label=label, label_width=80, label_cls="small"))

    svg.add(rect(206, 544, 1088, 176, fill="#fbfff7", stroke=GREEN, rx=36, pattern="dots-green", opacity=0.28))
    api_cards = [
        (252, "GET /tasks/{id}", "TaskRecord, status, steps"),
        (514, "GET /pending-actions", "PendingAction candidates"),
        (776, "POST Decision", "selected candidate, comment"),
        (1038, "GET /events", "EventLog + report metadata"),
    ]
    for x, title, body in api_cards:
        svg.add(card(x, 590, 206, 84, title, tuple(wrap(body, width=25)), fill="#ffffff", title_cls="mono-small"))
    svg.add(arrow(Point(756, 544), Point(1010, 444), color=GREEN, marker="arrow-green", dashed=True, label="server refresh after Decision", label_pos=Point(928, 510), label_width=230))
    svg.add(text(750, 754, "Web state is derived from API responses; it does not synthesize PendingAction, Decision, EventLog, or TaskSnapshot.", "mono-small", "middle"))

    (OUT_DIR / "frontend-workbench.svg").write_text(svg.render(), encoding="utf-8")


def main() -> None:
    """生成 README 使用的 SVG 架构图。"""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    render_system_architecture()
    render_workflow_swimlane()
    render_runtime_sequence()
    render_frontend_flow()


if __name__ == "__main__":
    main()
