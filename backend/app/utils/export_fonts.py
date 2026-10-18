"""Font and text helpers for DOCX/PDF exports.

The project runs on Windows/Python 3.9 in the user's environment, but tests may
run on Linux.  These helpers prefer system CJK fonts and sanitize characters
that commonly render as '?' in ReportLab/xhtml2pdf.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional


# A conservative replacement map.  ReportLab CID fonts and some Windows PDF
# viewers often show these as '?'.  Convert them before export.
_CHAR_REPLACEMENTS = {
    "✓": "OK",
    "✔": "OK",
    "✅": "OK",
    "✗": "X",
    "✘": "X",
    "→": "->",
    "⇒": "=>",
    "←": "<-",
    "↔": "<->",
    "•": "-",
    "·": "-",
    "●": "-",
    "◆": "-",
    "■": "-",
    "□": "-",
    "★": "*",
    "☆": "*",
    "⚠": "!",
    "◆": "-",
    "🔹": "-",
    "▶": "-",
    "▸": "-",
    "≤": "<=",
    "≥": ">=",
    "×": "x",
    "％": "%",
    "—": "-",
    "–": "-",
    "…": "...",
    """: '"',
    """: '"',
    "'": "'",
    "'": "'",
    "￥": "¥",
}

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "]+",
    flags=re.UNICODE,
)


def safe_export_text(value: object) -> str:
    """Return text safe for Word/PDF export.

    Keeps Chinese, ASCII and common punctuation, but removes emoji and replaces
    symbols that often become '?' in PDF output.
    """
    if value is None:
        return ""
    text = str(value)
    for old, new in _CHAR_REPLACEMENTS.items():
        text = text.replace(old, new)
    text = _EMOJI_RE.sub("", text)
    # Remove zero-width/control chars except line breaks and tabs.
    text = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)
    return text


def _candidate_cjk_fonts() -> list[str]:
    env = os.environ.get("PDF_CJK_FONT_PATH") or os.environ.get("CJK_FONT_PATH")
    candidates = []
    if env:
        candidates.append(env)
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidates.extend([
        str(Path(windir) / "Fonts" / "msyh.ttc"),
        str(Path(windir) / "Fonts" / "msyh.ttf"),
        str(Path(windir) / "Fonts" / "simsun.ttc"),
        str(Path(windir) / "Fonts" / "simhei.ttf"),
        str(Path(windir) / "Fonts" / "simfang.ttf"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ])
    return candidates


def register_pdf_cjk_font(font_name: str = "ResumeCJK") -> str:
    """Register a CJK font for ReportLab and return the font name.

    On Windows this uses Microsoft YaHei/Simsun; on Linux it uses Noto CJK.
    Falls back to ReportLab CID font only if no TrueType/OpenType CJK font exists.
    """
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    except Exception:
        return "STSong-Light"

    for path in _candidate_cjk_fonts():
        try:
            if path and Path(path).exists():
                pdfmetrics.registerFont(TTFont(font_name, path, subfontIndex=0))
                return font_name
        except Exception:
            continue

    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light"
    except Exception:
        return "Helvetica"


def set_docx_default_fonts(document, east_asia: str = "微软雅黑", latin: str = "Arial") -> None:
    """Set common DOCX styles to stable Chinese fonts."""
    try:
        from docx.shared import Pt
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except Exception:
        return

    for style_name in ("Normal", "Body Text", "List Paragraph"):
        try:
            style = document.styles[style_name]
        except Exception:
            continue
        try:
            style.font.name = latin
            style.font.size = Pt(10.5)
            rPr = style._element.get_or_add_rPr()
            rFonts = rPr.rFonts
            if rFonts is None:
                rFonts = OxmlElement("w:rFonts")
                rPr.append(rFonts)
            rFonts.set(qn("w:ascii"), latin)
            rFonts.set(qn("w:hAnsi"), latin)
            rFonts.set(qn("w:eastAsia"), east_asia)
            rFonts.set(qn("w:cs"), latin)
        except Exception:
            pass


def set_run_font(run, east_asia: str = "微软雅黑", latin: str = "Arial", size=None, bold: Optional[bool] = None) -> None:
    """Apply both Latin and East Asia fonts to a run."""
    try:
        from docx.oxml.ns import qn
        from docx.shared import Pt
    except Exception:
        return
    try:
        run.font.name = latin
        if size is not None:
            run.font.size = Pt(float(size)) if isinstance(size, (int, float)) else size
        if bold is not None:
            run.bold = bold
        if run._element.rPr is None:
            run._element.get_or_add_rPr()
        run._element.rPr.rFonts.set(qn("w:ascii"), latin)
        run._element.rPr.rFonts.set(qn("w:hAnsi"), latin)
        run._element.rPr.rFonts.set(qn("w:eastAsia"), east_asia)
        run._element.rPr.rFonts.set(qn("w:cs"), latin)
    except Exception:
        pass
