"""Generate the README architecture SVG using only the Python standard library.

Run: python docs/assets/generate_architecture.py
The PNG is a rendered export of this SVG, committed for GitHub compatibility.
"""

from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent


INK = "#172A39"
MUTED = "#59707E"
BLUE = "#2563EB"
TEAL = "#087F73"


def element(parent, tag, **attributes):
    """Create an SVG element with normalized attribute names."""
    return SubElement(parent, tag, {key.replace("_", "-"): str(value) for key, value in attributes.items()})


def text(parent, x, y, value, size=24, color=INK, weight=400):
    """Place text on an explicit baseline for predictable typography."""
    node = element(parent, "text", x=x, y=y, fill=color, font_size=size, font_weight=weight)
    node.text = value
    return node


def box(parent, x, y, width, height, fill="#FFFFFF", stroke="#D7E3E8", radius=18):
    """Draw one flat, rounded system boundary."""
    return element(parent, "rect", x=x, y=y, width=width, height=height, rx=radius, fill=fill, stroke=stroke, stroke_width=1.5)


def line(parent, path, color="#8DA4B1", dashed=False):
    """Draw a directional data flow with an optional integration style."""
    options = {"d": path, "fill": "none", "stroke": color, "stroke_width": 2.3, "marker_end": "url(#arrow)", "stroke_linejoin": "round"}
    if dashed:
        options["stroke_dasharray"] = "7 6"
    return element(parent, "path", **options)


def module(parent, x, y, width, height, label, title, rows, accent=TEAL):
    """Use the same hierarchy for every service or integration module."""
    box(parent, x, y, width, height)
    text(parent, x + 24, y + 35, label, 17, accent, 700)
    text(parent, x + 24, y + 76, title, 28, INK, 700)
    for index, row in enumerate(rows):
        text(parent, x + 24, y + 113 + index * 31, row, 21, MUTED)


def build_diagram():
    """Compose the actual SPA/API/services/storage and optional crawler topology."""
    svg = Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "width": "1600", "height": "1190", "viewBox": "0 0 1600 1190", "font-family": "Microsoft YaHei, Noto Sans CJK SC, Arial, sans-serif"})
    element(svg, "title").text = "ResumeMatch-AI 系统架构"
    element(svg, "desc").text = "React SPA 通过 FastAPI 编排解析、评分、改写和面试服务，使用 MySQL 持久化及外部 LLM；可选浏览器扩展导入岗位，Edge 与独立 CLI 采集招聘平台。"
    defs = element(svg, "defs")
    marker = element(defs, "marker", id="arrow", markerWidth=8, markerHeight=8, refX=7, refY=4, orient="auto", markerUnits="userSpaceOnUse")
    element(marker, "path", d="M 0 0 L 8 4 L 0 8 z", fill="#8DA4B1")

    box(svg, 0, 0, 1600, 1190, "#F6F9FB", "#F6F9FB", 0)
    box(svg, 64, 54, 7, 105, BLUE, BLUE, 2)
    text(svg, 94, 76, "RESUME INTELLIGENCE / SYSTEM MAP", 18, BLUE, 700)
    text(svg, 91, 139, "ResumeMatch-AI", 57, INK, 700)
    text(svg, 94, 183, "简历解析  →  岗位匹配  →  证据约束改写  →  模拟面试", 25, MUTED)

    box(svg, 64, 224, 1020, 126, "#EAF2FF", "#BCD2FB")
    text(svg, 90, 260, "01 / EXPERIENCE", 17, BLUE, 700)
    text(svg, 90, 304, "React + TypeScript", 32, INK, 700)
    text(svg, 504, 303, "上传 · JD · 报告 · 改写 · 面试", 25, MUTED)
    module(svg, 1140, 224, 396, 126, "OPTIONAL / IMPORT", "Chrome / Edge 扩展", ["岗位导入 → 后端 API"], BLUE)

    line(svg, "M 574 350 V 404")
    line(svg, "M 1200 350 V 377 H 1018 V 404", dashed=True)

    box(svg, 64, 404, 1020, 112, "#16384B", "#16384B")
    text(svg, 90, 439, "02 / ORCHESTRATION", 17, "#A6D8F1", 700)
    text(svg, 90, 481, "FastAPI  /api/v1", 32, "#FFFFFF", 700)
    text(svg, 570, 478, "请求校验  ·  业务编排  ·  数据访问", 23, "#D3E4ED")
    line(svg, "M 1084 460 H 1140", dashed=True)
    module(svg, 1140, 404, 396, 144, "OPTIONAL / WEB CRAWLER", "Playwright + Edge CDP", ["专用浏览器 · 登录态 · 岗位采集"], BLUE)

    element(svg, "path", d="M 574 516 V 545 H 224 M 574 545 H 924", fill="none", stroke="#8DA4B1", stroke_width=2.3)
    for center in (224, 574, 924):
        line(svg, f"M {center} 545 V 574")
    module(svg, 64, 574, 320, 210, "03A / UNDERSTAND", "结构化解析", ["PDF 文本 / 可选 OCR", "简历与 JD 信息抽取", "技能别名归一化"])
    module(svg, 414, 574, 320, 210, "03B / EVALUATE", "评分与诊断", ["技能 40% · 项目 25%", "文本 20% · 要求 15%", "差距识别 · 问题证据"])
    module(svg, 764, 574, 320, 210, "03C / IMPROVE", "改写与面试", ["证据链 · 改写质量检查", "可编辑简历 · 报告导出", "题库 · 回答评分 · 追问"])

    line(svg, "M 1338 548 V 604", dashed=True)
    module(svg, 1140, 604, 396, 148, "EXTERNAL / JOB SOURCES", "招聘平台", ["BOSS · 智联 · 猎聘 · 前程无忧"], BLUE)

    element(svg, "path", d="M 224 784 V 817 H 574 M 924 784 V 817 H 574", fill="none", stroke="#8DA4B1", stroke_width=2.3)
    element(svg, "path", d="M 574 784 V 838 H 309 M 574 838 H 839", fill="none", stroke="#8DA4B1", stroke_width=2.3)
    line(svg, "M 309 838 V 864")
    line(svg, "M 839 838 V 864")
    module(svg, 64, 864, 490, 146, "04 / PERSISTENCE", "MySQL 8 + SQLAlchemy", ["简历 · JD · 任务 · 报告 · 改写 · 缓存"])
    module(svg, 594, 864, 490, 146, "04 / MODEL PROVIDERS", "DeepSeek / OpenAI-compatible", ["解析与生成调用；mock 提供规则流程"])
    module(svg, 1140, 864, 396, 146, "OPTIONAL / STANDALONE", "job_crawler CLI", ["独立采集 → 排序 → 多格式导出"], BLUE)
    line(svg, "M 1338 864 V 752", dashed=True)

    element(svg, "path", d="M 64 1064 H 1536", stroke="#D7E3E8", stroke_width=1.5)
    text(svg, 64, 1110, "DESIGN PRINCIPLES", 17, BLUE, 700)
    text(svg, 328, 1110, "评分可解释", 25, INK, 700)
    text(svg, 641, 1110, "生成有证据", 25, INK, 700)
    text(svg, 954, 1110, "结果可编辑", 25, INK, 700)
    text(svg, 64, 1154, "实线：应用主流程   /   虚线：可选集成     ·     评分可使用本地句向量或词频余弦相似度", 19, MUTED)
    return svg


def main():
    """Write the editable vector next to this script."""
    path = Path(__file__).with_name("architecture.svg")
    tree = ElementTree(build_diagram())
    indent(tree)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    print(path)


if __name__ == "__main__":
    main()
