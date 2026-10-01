"""Safe, deterministic report exports for Markdown, Word and PDF."""

import io
import re
from pathlib import Path
from typing import Literal
from xml.sax.saxutils import escape

from docx import Document
from docx.shared import Inches, Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ReportFormat = Literal["md", "docx", "pdf"]


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
    for line in content.replace("\r\n", "\n").split("\n"):
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
            document.add_paragraph(re.sub(r"^[-*]\s+", "", stripped), style="List Bullet")
        else:
            document.add_paragraph(stripped)
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
    for line in content.replace("\r\n", "\n").split("\n"):
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
        story.append(Paragraph(escape(stripped), style))
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
