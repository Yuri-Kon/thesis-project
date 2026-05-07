from __future__ import annotations

from drawio_common import (
    EDGE,
    EDGE_DASHED,
    FIGURES_DIR,
    Diagram,
    Node,
    box_style,
    diamond_style,
    ellipse_style,
    text_style,
)


WIDTH = 2100
HEIGHT = 1500
LEFT = 60
TOP = 70
TITLE_H = 78
HEADER_H = 70
BODY_TOP = TOP + TITLE_H + HEADER_H
BODY_H = 1190

LANES = [
    ("Human / UI", 260, "#EFF6FF", "#2563EB"),
    ("TaskAPI", 240, "#F8FAFC", "#64748B"),
    ("Workflow / FSM", 320, "#F5F3FF", "#7C3AED"),
    ("PlannerAgent", 285, "#FFFBEB", "#D97706"),
    ("Executor / Tools", 335, "#F0FDF4", "#15803D"),
    ("SafetyAgent", 285, "#FFF1F2", "#E11D48"),
    ("Storage / Log", 280, "#F1F5F9", "#475569"),
]


def render() -> None:
    """生成竖向泳道风格的任务生命周期图。

    该脚本只写出 workflow-swimlane.drawio，不会覆盖其他图。
    """

    d = Diagram("Workflow Swimlane", WIDTH, HEIGHT)
    draw_frame(d)
    centers = lane_centers()

    nodes = {
        "submit": oval(d, "Human / UI", "Submit<br>goal + constraints", 205, w=190, fill="#DBEAFE", stroke="#2563EB"),
        "create": box(d, "TaskAPI", "Validate schema<br>Create TaskRecord", 205, w=190, fill="#E0F2FE", stroke="#0284C7"),
        "created": box(d, "Workflow / FSM", "CREATED → PLANNING", 205, w=210, fill="#EDE9FE", stroke="#7C3AED"),
        "plan": box(d, "PlannerAgent", "Generate Top-K<br>Plan candidates", 205, w=210, fill="#FEF3C7", stroke="#D97706"),
        "plan_gate": diamond(d, "Workflow / FSM", "Plan<br>confirmation<br>required?", 375, w=210, h=120, fill="#FFF7ED", stroke="#F97316"),
        "snapshot_plan": box(d, "Storage / Log", "Persist PendingAction<br>+ TaskSnapshot", 365, w=215, fill="#E2E8F0", stroke="#475569"),
        "review_plan": box(d, "Human / UI", "Review candidates<br>Submit Decision", 430, w=205, fill="#DBEAFE", stroke="#2563EB"),
        "planned": box(d, "Workflow / FSM", "PLANNED<br>Decision applied", 570, w=210, fill="#DCFCE7", stroke="#15803D"),
        "run": box(d, "Executor / Tools", "RUNNING<br>Run PlanStep", 570, w=230, fill="#DCFCE7", stroke="#15803D"),
        "safety": diamond(d, "SafetyAgent", "Safety<br>allow / warn / block?", 570, w=210, h=120, fill="#FFE4E6", stroke="#E11D48"),
        "step_ok": diamond(d, "Workflow / FSM", "Step<br>finished?", 760, w=190, h=110, fill="#F0FDFA", stroke="#0F766E"),
        "retry": box(d, "Executor / Tools", "Retry / local failure<br>stop further tools", 790, w=235, fill="#FFEDD5", stroke="#F97316"),
        "patch": box(d, "PlannerAgent", "Generate Patch /<br>Replan candidates", 790, w=225, fill="#FEF3C7", stroke="#D97706"),
        "wait_recovery": box(d, "Workflow / FSM", "WAITING_PATCH_CONFIRM<br>or WAITING_REPLAN_CONFIRM", 955, w=270, fill="#FFE4E6", stroke="#E11D48"),
        "snapshot_recovery": box(d, "Storage / Log", "Write EventLog<br>+ recovery Snapshot", 955, w=215, fill="#E2E8F0", stroke="#475569"),
        "review_recovery": box(d, "Human / UI", "Approve / Replan<br>Cancel / Continue", 1035, w=205, fill="#DBEAFE", stroke="#2563EB"),
        "summarizing": box(d, "Workflow / FSM", "SUMMARIZING", 1190, w=210, fill="#E0F2FE", stroke="#0284C7"),
        "summary": box(d, "Executor / Tools", "SummarizerAgent<br>DesignResult + report", 1190, w=245, fill="#E0F2FE", stroke="#0284C7"),
        "final_store": box(d, "Storage / Log", "Persist report<br>artifacts / timeline", 1190, w=215, fill="#E2E8F0", stroke="#475569"),
        "done": oval(d, "Human / UI", "View report<br>DONE", 1335, w=190, fill="#DCFCE7", stroke="#15803D"),
        "terminal": oval(d, "Workflow / FSM", "FAILED / CANCELLED<br>terminal", 1335, w=220, fill="#FEE2E2", stroke="#DC2626"),
    }

    draw_edges(d, nodes, centers)
    draw_legend(d)
    d.save(FIGURES_DIR / "workflow-swimlane.drawio")


def draw_frame(d: Diagram) -> None:
    """绘制外框、标题与竖向泳道。"""

    total_w = sum(width for _, width, _, _ in LANES)
    d.node("", LEFT, TOP, total_w, TITLE_H + HEADER_H + BODY_H, style="rounded=0;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#64748B;strokeWidth=2;", prefix="frame")
    d.node("任务生命周期泳道图：FSM、HITL 与恢复闭环", LEFT, TOP, total_w, TITLE_H, style="rounded=0;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#64748B;strokeWidth=1.4;fontFamily=Helvetica;fontSize=25;fontStyle=1;align=center;verticalAlign=middle;", prefix="title")

    x = LEFT
    for label, lane_w, fill, stroke in LANES:
        d.node(label, x, TOP + TITLE_H, lane_w, HEADER_H, style=f"rounded=0;whiteSpace=wrap;html=1;fillColor={fill};strokeColor=#64748B;strokeWidth=1.4;fontFamily=Helvetica;fontSize=18;fontStyle=1;fontColor=#0F172A;align=center;verticalAlign=middle;", prefix="head")
        d.node("", x, BODY_TOP, lane_w, BODY_H, style=f"rounded=0;whiteSpace=wrap;html=1;fillColor={fill};strokeColor=#CBD5E1;strokeWidth=1;", prefix="lane")
        d.node("", x, TOP + TITLE_H, 1, HEADER_H + BODY_H, style=f"shape=line;strokeColor={stroke};strokeWidth=1.2;html=1;", prefix="lane_sep")
        x += lane_w
    d.node("", x, TOP + TITLE_H, 1, HEADER_H + BODY_H, style="shape=line;strokeColor=#64748B;strokeWidth=1.4;html=1;", prefix="lane_sep")


def lane_centers() -> dict[str, int]:
    """返回每个泳道中心 x 坐标。"""

    centers: dict[str, int] = {}
    x = LEFT
    for label, lane_w, _, _ in LANES:
        centers[label] = x + lane_w // 2
        x += lane_w
    return centers


def box(
    d: Diagram,
    lane: str,
    label: str,
    y: int,
    *,
    w: int,
    h: int = 78,
    fill: str,
    stroke: str,
) -> Node:
    x = lane_centers()[lane] - w // 2
    return d.node(label, x, BODY_TOP + y, w, h, style=box_style(fill, stroke, font_size=13), prefix="act")


def oval(
    d: Diagram,
    lane: str,
    label: str,
    y: int,
    *,
    w: int,
    h: int = 78,
    fill: str,
    stroke: str,
) -> Node:
    x = lane_centers()[lane] - w // 2
    return d.node(label, x, BODY_TOP + y, w, h, style=ellipse_style(fill, stroke, font_size=13), prefix="oval")


def diamond(
    d: Diagram,
    lane: str,
    label: str,
    y: int,
    *,
    w: int,
    h: int,
    fill: str,
    stroke: str,
) -> Node:
    x = lane_centers()[lane] - w // 2
    return d.node(label, x, BODY_TOP + y, w, h, style=diamond_style(fill, stroke, font_size=13), prefix="dec")


def draw_edges(d: Diagram, n: dict[str, Node], centers: dict[str, int]) -> None:
    """绘制正交连线，尽量沿泳道中心和空白带走线。"""

    right_bus = LEFT + sum(width for _, width, _, _ in LANES) - 80
    left_bus = LEFT + 45

    d.edge(n["submit"], n["create"], "")
    d.edge(n["create"], n["created"], "")
    d.edge(n["created"], n["plan"], "planning request")
    d.edge(n["plan"], n["plan_gate"], "CandidateSet", points=[(centers["PlannerAgent"], BODY_TOP + 335), (centers["Workflow / FSM"], BODY_TOP + 335)])
    d.edge(n["plan_gate"], n["snapshot_plan"], "Yes: wait", points=[(centers["Workflow / FSM"], BODY_TOP + 430), (centers["Storage / Log"], BODY_TOP + 430)])
    d.edge(n["snapshot_plan"], n["review_plan"], "expose PendingAction", style=EDGE_DASHED, points=[(centers["Storage / Log"], BODY_TOP + 525), (centers["Human / UI"], BODY_TOP + 525)])
    d.edge(n["review_plan"], n["planned"], "accept", points=[(centers["Human / UI"], BODY_TOP + 645), (centers["Workflow / FSM"], BODY_TOP + 645)])
    d.edge(n["plan_gate"], n["planned"], "No: auto", points=[(centers["Workflow / FSM"], BODY_TOP + 540)])
    d.edge(n["planned"], n["run"], "")
    d.edge(n["run"], n["safety"], "pre/post check")
    d.edge(n["safety"], n["step_ok"], "allow / warn", points=[(centers["SafetyAgent"], BODY_TOP + 735), (centers["Workflow / FSM"], BODY_TOP + 735)])
    d.edge(n["step_ok"], n["run"], "more steps", style=EDGE_DASHED, points=[(centers["Workflow / FSM"], BODY_TOP + 900), (right_bus, BODY_TOP + 900), (right_bus, BODY_TOP + 610), (centers["Executor / Tools"], BODY_TOP + 610)])
    d.edge(n["step_ok"], n["retry"], "failure / retry exhausted", points=[(centers["Workflow / FSM"], BODY_TOP + 850), (centers["Executor / Tools"], BODY_TOP + 850)])
    d.edge(n["safety"], n["patch"], "block / replan", points=[(centers["SafetyAgent"], BODY_TOP + 750), (centers["PlannerAgent"], BODY_TOP + 750)])
    d.edge(n["retry"], n["patch"], "patch request")
    d.edge(n["patch"], n["wait_recovery"], "Patch/Replan candidates", points=[(centers["PlannerAgent"], BODY_TOP + 935), (centers["Workflow / FSM"], BODY_TOP + 935)])
    d.edge(n["wait_recovery"], n["snapshot_recovery"], "persist before wait", points=[(centers["Workflow / FSM"], BODY_TOP + 1010), (centers["Storage / Log"], BODY_TOP + 1010)])
    d.edge(n["snapshot_recovery"], n["review_recovery"], "decision needed", style=EDGE_DASHED, points=[(centers["Storage / Log"], BODY_TOP + 1115), (centers["Human / UI"], BODY_TOP + 1115)])
    d.edge(n["review_recovery"], n["run"], "resume RUNNING", style=EDGE_DASHED, points=[(left_bus, BODY_TOP + 1165), (left_bus, BODY_TOP + 620), (centers["Executor / Tools"], BODY_TOP + 620)])
    d.edge(n["review_recovery"], n["terminal"], "cancel / terminal_stop", style=EDGE_DASHED, points=[(centers["Human / UI"], BODY_TOP + 1295), (centers["Workflow / FSM"], BODY_TOP + 1295)])
    d.edge(n["step_ok"], n["summarizing"], "all steps done", points=[(centers["Workflow / FSM"], BODY_TOP + 1125)])
    d.edge(n["summarizing"], n["summary"], "")
    d.edge(n["summary"], n["final_store"], "reports / artifacts")
    d.edge(n["final_store"], n["done"], "timeline + report", points=[(centers["Storage / Log"], BODY_TOP + 1380), (centers["Human / UI"], BODY_TOP + 1380)])


def draw_legend(d: Diagram) -> None:
    """绘制图例。"""

    y = BODY_TOP + BODY_H - 58
    x = LEFT + 20
    items = [
        ("HITL / WAITING", "#FFE4E6", "#E11D48"),
        ("Planning", "#FEF3C7", "#D97706"),
        ("Execution", "#DCFCE7", "#15803D"),
        ("Persistence", "#E2E8F0", "#475569"),
    ]
    for label, fill, stroke in items:
        d.node("", x, y, 26, 18, style=f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=1.4;", prefix="legend")
        d.node(label, x + 34, y - 2, 150, 24, style=text_style(font_size=11, color="#475569", align="left"), prefix="legend_text")
        x += 200
    d.node(
        "Invariant: WAITING_* states are paused; TaskSnapshot/EventLog are written before human Decision is requested.",
        LEFT + 900,
        y - 4,
        760,
        30,
        style=text_style(font_size=11, color="#64748B", align="right"),
        prefix="note",
    )


if __name__ == "__main__":
    render()
