from __future__ import annotations

from drawio_common import (
    EDGE,
    EDGE_DASHED,
    FIGURES_DIR,
    Diagram,
    Node,
    box_style,
    text_style,
)


WIDTH = 2600
HEIGHT = 1800
TOP = 60
LEFT = 70
OBJ_TOP = 140
OBJ_H = 66
LIFE_TOP = OBJ_TOP + OBJ_H
LIFE_BOTTOM = 1660
ACT_W = 18

OBJECTS = [
    ("U", "Researcher", 120),
    ("API", "TaskAPI / UI", 340),
    ("WF", "Workflow / FSM", 590),
    ("P", "PlannerAgent", 835),
    ("KG", "ToolKG / LLM", 1065),
    ("EX", "ExecutorAgent", 1305),
    ("ST", "StepRunner", 1535),
    ("AD", "ToolAdapter", 1765),
    ("SA", "SafetyAgent", 1995),
    ("DS", "EventLog / Snapshot", 2235),
    ("SU", "SummarizerAgent", 2470),
]


def render() -> None:
    """生成 UML 风格时序图。

    该脚本只写出 runtime-sequence.drawio，不会覆盖其他图。
    """

    d = Diagram("Runtime Sequence", WIDTH, HEIGHT)
    draw_title(d)
    draw_objects(d)
    draw_activations(d)
    draw_fragments(d)
    draw_messages(d)
    draw_legend(d)
    d.save(FIGURES_DIR / "runtime-sequence.drawio")


def draw_title(d: Diagram) -> None:
    d.node(
        "时序图：端到端规划、执行、HITL 与恢复闭环",
        LEFT,
        TOP,
        WIDTH - LEFT * 2,
        38,
        style="text;html=1;strokeColor=none;fillColor=none;fontSize=24;fontStyle=1;fontFamily=Helvetica;align=center;",
        prefix="title",
    )
    d.node(
        "Object / Lifeline / Message / Activation 均显式绘制；消息自上而下表示执行先后顺序，WAITING_* 分支表示执行暂停。",
        LEFT,
        TOP + 42,
        WIDTH - LEFT * 2,
        28,
        style=text_style(font_size=12, color="#64748B"),
        prefix="subtitle",
    )


def draw_objects(d: Diagram) -> None:
    for key, label, x in OBJECTS:
        d.node(label, x - 78, OBJ_TOP, 156, OBJ_H, style=box_style("#F8FAFC", "#334155", font_size=12), prefix=f"obj_{key}")
        d.node(
            "",
            x,
            LIFE_TOP,
            1,
            LIFE_BOTTOM - LIFE_TOP,
            style="shape=line;strokeColor=#94A3B8;strokeWidth=1.2;dashed=1;html=1;",
            prefix=f"life_{key}",
        )


def draw_activations(d: Diagram) -> None:
    activations = {
        "API": [(250, 500), (660, 765), (940, 1075), (1340, 1465)],
        "WF": [(300, 835), (1070, 1235)],
        "P": [(350, 575), (1115, 1220)],
        "KG": [(430, 515)],
        "EX": [(835, 1395)],
        "ST": [(925, 1110), (1240, 1325)],
        "AD": [(995, 1055)],
        "SA": [(885, 930), (1060, 1105)],
        "DS": [(610, 720), (1150, 1205), (1430, 1505)],
        "SU": [(1400, 1485)],
    }
    x_lookup = {key: x for key, _, x in OBJECTS}
    for key, ranges in activations.items():
        for start, end in ranges:
            x = x_lookup[key] - ACT_W // 2
            d.node("", x, start, ACT_W, end - start, style="rounded=0;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#111827;strokeWidth=1.4;", prefix=f"act_{key}")


def draw_fragments(d: Diagram) -> None:
    frame_style = "rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#94A3B8;strokeWidth=1.2;dashed=1;"
    d.node("", 525, 585, 1870, 190, style=frame_style, prefix="frag")
    d.node("alt plan gate requires HITL", 540, 592, 250, 26, style=text_style(font_size=12, color="#475569", align="left"), prefix="frag_label")
    d.node("", 1260, 875, 860, 475, style=frame_style, prefix="frag")
    d.node("loop for each PlanStep / alt recovery", 1275, 882, 300, 26, style=text_style(font_size=12, color="#475569", align="left"), prefix="frag_label")
    d.node("", 1185, 1130, 1120, 160, style=frame_style, prefix="frag")
    d.node("alt retry exhausted or safety block", 1200, 1137, 310, 26, style=text_style(font_size=12, color="#475569", align="left"), prefix="frag_label")


def point(d: Diagram, key: str, y: int) -> Node:
    x_lookup = {obj_key: x for obj_key, _, x in OBJECTS}
    return d.node("", x_lookup[key], y, 1, 1, style="shape=ellipse;fillColor=none;strokeColor=none;", prefix="msg")


def message(
    d: Diagram,
    src: str,
    dst: str,
    y: int,
    label: str,
    *,
    dashed: bool = False,
    points: list[tuple[int, int]] | None = None,
) -> None:
    d.edge(point(d, src, y), point(d, dst, y), label, style=EDGE_DASHED if dashed else EDGE, points=points)


def self_message(d: Diagram, key: str, y: int, label: str, *, dashed: bool = False) -> None:
    x_lookup = {obj_key: x for obj_key, _, x in OBJECTS}
    x = x_lookup[key]
    start = d.node("", x, y, 1, 1, style="shape=ellipse;fillColor=none;strokeColor=none;", prefix="self")
    end = d.node("", x, y + 54, 1, 1, style="shape=ellipse;fillColor=none;strokeColor=none;", prefix="self")
    style = EDGE_DASHED if dashed else EDGE
    d.edge(start, end, label, style=style, points=[(x + 80, y), (x + 80, y + 54)])


def draw_messages(d: Diagram) -> None:
    message(d, "U", "API", 260, "1. POST /tasks(goal, constraints)")
    message(d, "API", "WF", 315, "2. create ProteinDesignTask + TaskRecord(CREATED)")
    message(d, "WF", "P", 370, "3. plan_with_status(task, context, record)")
    message(d, "P", "KG", 445, "4. retrieve tools, schemas, cost, safety")
    message(d, "KG", "P", 520, "5. tool candidates + provider route", dashed=True)
    message(d, "P", "WF", 575, "6. Top-K PlanCandidates + default", dashed=True)
    message(d, "WF", "DS", 635, "7. PENDING_ACTION_CREATED + WAITING_ENTER")
    message(d, "WF", "DS", 700, "8. write TaskSnapshot(plan_confirm)")
    message(d, "WF", "API", 760, "9. status = WAITING_PLAN_CONFIRM", dashed=True)
    message(d, "U", "API", 835, "10. POST /pending-actions/{id}/decision")
    message(d, "API", "WF", 890, "11. validate Decision + apply_plan_confirm_decision")
    message(d, "WF", "DS", 950, "12. DECISION_APPLIED + WAITING_EXIT")
    message(d, "WF", "EX", 1010, "13. run confirmed Plan")
    message(d, "EX", "SA", 1070, "14. check_task_input / pre-step safety")
    message(d, "EX", "ST", 1135, "15. run_step_with_patch(step_k)")
    message(d, "ST", "AD", 1195, "16. resolve_inputs + run(tool, inputs)")
    message(d, "AD", "ST", 1255, "17. outputs / metrics or error", dashed=True)
    message(d, "ST", "SA", 1315, "18. post_step safety(step_result)")
    message(d, "ST", "DS", 1375, "19. STEP_FINISHED / STEP_FAILED + runtime_state")
    message(d, "EX", "P", 1440, "20. patch_top_k / replan_top_k if recovery needed")
    message(d, "P", "EX", 1500, "21. Patch/Replan candidates", dashed=True)
    message(d, "EX", "DS", 1560, "22. WAITING_ENTER + TaskSnapshot before Decision")
    self_message(d, "EX", 1285, "retry/backoff if attempts remain", dashed=True)
    message(d, "EX", "SU", 1630, "23. summarize_and_finalize(context)")
    message(d, "SU", "DS", 1685, "24. report metadata / execution summary")
    message(d, "SU", "API", 1735, "25. DesignResult + report_path", dashed=True, points=[(2470, 1765), (340, 1765)])
    message(d, "API", "U", 1775, "26. TaskRecord(status, pending_action, report_path)", dashed=True)


def draw_legend(d: Diagram) -> None:
    y = 103
    d.node("Object", 92, y, 92, 28, style=box_style("#F8FAFC", "#334155", font_size=11), prefix="legend")
    d.node("", 230, y - 3, 1, 34, style="shape=line;strokeColor=#94A3B8;strokeWidth=1.2;dashed=1;html=1;", prefix="legend")
    d.node("Lifeline", 244, y, 90, 28, style=text_style(font_size=11, color="#475569", align="left"), prefix="legend")
    d.node("", 385, y - 3, 18, 34, style="rounded=0;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#111827;strokeWidth=1.4;", prefix="legend")
    d.node("Activation", 412, y, 100, 28, style=text_style(font_size=11, color="#475569", align="left"), prefix="legend")
    d.node("solid: call / dashed: return or resume", 570, y, 250, 28, style=text_style(font_size=11, color="#475569", align="left"), prefix="legend")


if __name__ == "__main__":
    render()
