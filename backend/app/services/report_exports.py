"""Safe, deterministic report exports for Markdown, Word and PDF."""

import io
import re
from pathlib import Path
from typing import Literal
from xml.sax.saxutils import escape

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

ReportFormat = Literal["md", "docx", "pdf"]

_INLINE = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)|\*\*([^*\n]+)\*\*|`([^`\n]+)`")


def _word_text(paragraph, text: str) -> None:
    start = 0
    for match in _INLINE.finditer(text):
        paragraph.add_run(text[start:match.start()])
        if match.group(3) is not None:
            paragraph.add_run(match.group(3)).bold = True
        elif match.group(4) is not None:
            paragraph.add_run(match.group(4))
        else:
            link = OxmlElement("w:hyperlink")
            link.set(qn("r:id"), paragraph.part.relate_to(
                match.group(2), RELATIONSHIP_TYPE.HYPERLINK, is_external=True,
            ))
            run = OxmlElement("w:r")
            properties = OxmlElement("w:rPr")
            style = OxmlElement("w:rStyle")
            style.set(qn("w:val"), "Hyperlink")
            properties.append(style)
            run.append(properties)
            value = OxmlElement("w:t")
            value.text = match.group(1)
            run.append(value)
            link.append(run)
            paragraph._p.append(link)
        start = match.end()
    paragraph.add_run(text[start:])


def _pdf_text(text: str) -> str:
    parts, start = [], 0
    for match in _INLINE.finditer(text):
        parts.append(escape(text[start:match.start()]))
        if match.group(3) is not None:
            # The Unicode body font has no separately registered bold face.
            parts.append(escape(match.group(3)))
        elif match.group(4) is not None:
            parts.append(escape(match.group(4)))
        else:
            url = escape(match.group(2), {'"': '&quot;'})
            parts.append(f'<link href="{url}" color="#155E75">{escape(match.group(1))}</link>')
        start = match.end()
    parts.append(escape(text[start:]))
    return "".join(parts)


def _blocks(content: str):
    """Recognize valid Markdown tables; preserve malformed input as text."""
    lines = content.replace("\r\n", "\n").split("\n")
    index = 0
    while index < len(lines):
        def cells(line):
            return [part.strip().replace(r"\|", "|") for part in
                    re.split(r"(?<!\\)\|", line.strip().strip("|"))]

        header = cells(lines[index])
        if index + 1 < len(lines) and "|" in lines[index]:
            separator = cells(lines[index + 1])
            if len(header) == len(separator) and all(
                re.fullmatch(r":?-{3,}:?", cell) for cell in separator
            ):
                rows = [header]
                index += 2
                while index < len(lines) and "|" in lines[index]:
                    row = cells(lines[index])
                    if len(row) != len(header):
                        break
                    rows.append(row)
                    index += 1
                yield "table", rows
                continue
        yield "line", lines[index]
        index += 1


def _lines(title: str, content: str) -> list[str]:
    return [title.strip(), *content.replace("\r\n", "\n").split("\n")]


def export_markdown(title: str, content: str) -> bytes:
    return f"# {title.strip()}\n\n{content.rstrip()}\n".encode()


def export_docx(title: str, content: str) -> bytes:
    document = Document()
    section = document.sections[0]
    section.top_margin = section.bottom_margin = Inches(0.8)
    section.left_margin = section.right_margin = Inches(0.85)
    document.styles["Normal"].font.name = "Arial"
    document.styles["Normal"].font.size = Pt(10.5)
    document.add_heading(title.strip(), level=0)
    for kind, value in _blocks(content):
        if kind == "table":
            table = document.add_table(rows=1, cols=len(value[0]))
            table.style = "Light Shading Accent 1"
            repeat_header = OxmlElement("w:tblHeader")
            table.rows[0]._tr.get_or_add_trPr().append(repeat_header)
            for cell, text in zip(table.rows[0].cells, value[0], strict=True):
                _word_text(cell.paragraphs[0], text)
            for row in value[1:]:
                for cell, text in zip(table.add_row().cells, row, strict=True):
                    _word_text(cell.paragraphs[0], text)
            document.add_paragraph()
            continue
        line = value
        stripped = line.strip()
        if not stripped:
            document.add_paragraph()
        elif stripped.startswith("### "):
            document.add_heading(stripped[4:], level=3)
        elif stripped.startswith("## "):
            document.add_heading(stripped[3:], level=2)
        elif stripped.startswith("# "):
            document.add_heading(stripped[2:], level=1)
        elif re.match(r"^[-*]\s+", stripped):
            _word_text(document.add_paragraph(style="List Bullet"),
                       re.sub(r"^[-*]\s+", "", stripped))
        else:
            _word_text(document.add_paragraph(), stripped)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _pdf_font() -> str:
    for candidate in (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if candidate.exists():
            name = "DriveAgentUnicode"
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(candidate)))
            return name
    return "Helvetica"


def export_pdf(title: str, content: str) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=48,
        leftMargin=48,
        topMargin=48,
        bottomMargin=48,
        title=title.strip(),
        author="Veridra",
    )
    styles = getSampleStyleSheet()
    font = _pdf_font()
    for style_name in ("Title", "Heading1", "Heading2", "Heading3", "BodyText"):
        styles[style_name].fontName = font
    story = [Paragraph(escape(title.strip()), styles["Title"]), Spacer(1, 12)]
    for kind, value in _blocks(content):
        if kind == "table":
            rows = [[Paragraph(_pdf_text(cell), styles["BodyText"]) for cell in row]
                    for row in value]
            table = LongTable(rows, colWidths=[document.width / len(value[0])] * len(value[0]),
                              repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]))
            story.extend([table, Spacer(1, 10)])
            continue
        line = value
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 8))
            continue
        style = styles["BodyText"]
        for marker, heading in (("### ", "Heading3"), ("## ", "Heading2"), ("# ", "Heading1")):
            if stripped.startswith(marker):
                stripped, style = stripped[len(marker) :], styles[heading]
                break
        if re.match(r"^[-*]\s+", stripped):
            stripped = "• " + re.sub(r"^[-*]\s+", "", stripped)
        story.append(Paragraph(_pdf_text(stripped), style))
        story.append(Spacer(1, 5))
    document.build(story)
    return buffer.getvalue()


def export_report(title: str, content: str, output_format: ReportFormat) -> tuple[bytes, str]:
    if output_format == "md":
        return export_markdown(title, content), "text/markdown; charset=utf-8"
    if output_format == "docx":
        return export_docx(title, content), (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    return export_pdf(title, content), "application/pdf"
