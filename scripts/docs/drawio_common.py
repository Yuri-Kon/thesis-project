from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
FIGURES_DIR = ROOT / "asserts" / "figures"

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
        f"fillColor={fill};strokeColor={stroke};strokeWidth=1.5;"
        f"fontFamily=Helvetica;fontSize={font_size};align=center;verticalAlign=middle;spacing=8;"
    )


def ellipse_style(fill: str, stroke: str = "#334155", *, font_size: int = 13) -> str:
    """创建椭圆节点样式。"""

    return (
        "ellipse;whiteSpace=wrap;html=1;"
        f"fillColor={fill};strokeColor={stroke};strokeWidth=1.6;"
        f"fontFamily=Helvetica;fontSize={font_size};align=center;verticalAlign=middle;spacing=8;"
    )


def diamond_style(fill: str, stroke: str, *, font_size: int = 13) -> str:
    """创建判断节点样式。"""

    return (
        "rhombus;whiteSpace=wrap;html=1;"
        f"fillColor={fill};strokeColor={stroke};strokeWidth=1.6;"
        f"fontFamily=Helvetica;fontSize={font_size};align=center;verticalAlign=middle;spacing=8;"
    )


def text_style(*, font_size: int = 12, color: str = "#475569", align: str = "center") -> str:
    """创建无边框文本样式。"""

    return f"text;html=1;strokeColor=none;fillColor=none;fontSize={font_size};fontColor={color};align={align};"
