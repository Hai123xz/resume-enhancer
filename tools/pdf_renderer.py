from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape as escape_html

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

FONT_DIR = Path(__file__).resolve().parents[1] / "fonts"

REGULAR_FONT = "DejaVuSans"
BOLD_FONT = "DejaVuSans-Bold"
MONO_FONT = "DejaVuSansMono"

FALLBACK_BODY_FONT = "Helvetica"
FALLBACK_BOLD_FONT = "Helvetica-Bold"
FALLBACK_MONO_FONT = "Courier"


def _register_fonts() -> tuple[str, str, str]:
    """Register local fonts if available, otherwise fall back to built-ins."""
    regular_path = FONT_DIR / "DejaVuSans.ttf"
    bold_path = FONT_DIR / "DejaVuSans-Bold.ttf"
    mono_path = FONT_DIR / "DejaVuSansMono.ttf"

    registered = set(pdfmetrics.getRegisteredFontNames())

    try:
        if regular_path.exists() and REGULAR_FONT not in registered:
            pdfmetrics.registerFont(TTFont(REGULAR_FONT, str(regular_path)))
        if bold_path.exists() and BOLD_FONT not in registered:
            pdfmetrics.registerFont(TTFont(BOLD_FONT, str(bold_path)))
        if mono_path.exists() and MONO_FONT not in registered:
            pdfmetrics.registerFont(TTFont(MONO_FONT, str(mono_path)))

        if regular_path.exists() and bold_path.exists():
            registerFontFamily(
                REGULAR_FONT,
                normal=REGULAR_FONT,
                bold=BOLD_FONT,
                italic=REGULAR_FONT,
                boldItalic=BOLD_FONT,
            )
    except Exception:
        # Fall back to built-in fonts if anything goes wrong.
        pass

    body_font = REGULAR_FONT if REGULAR_FONT in pdfmetrics.getRegisteredFontNames() else FALLBACK_BODY_FONT
    bold_font = BOLD_FONT if BOLD_FONT in pdfmetrics.getRegisteredFontNames() else FALLBACK_BOLD_FONT
    mono_font = MONO_FONT if MONO_FONT in pdfmetrics.getRegisteredFontNames() else FALLBACK_MONO_FONT

    return body_font, bold_font, mono_font


def _inline_markdown_to_html(text: str, code_font: str) -> str:
    """
    Convert a small subset of markdown to ReportLab-friendly HTML.
    Supports:
    - **bold**
    - *italic*
    - `code`
    """
    text = escape_html(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(.+?)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", rf'<font face="{code_font}">\1</font>', text)
    return text


def _parse_blocks(text: str) -> list[tuple[str, str]]:
    """
    Turn markdown-ish text into renderable blocks.

    Returns a list of tuples:
    - ("heading1" | "heading2" | "heading3", content)
    - ("paragraph", content)
    - ("bullet", content)
    - ("spacer", "")
    """
    blocks: list[tuple[str, str]] = []
    paragraph_lines: list[str] = []

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            blocks.append(("paragraph", " ".join(paragraph_lines).strip()))
            paragraph_lines = []

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            flush_paragraph()
            blocks.append(("spacer", ""))
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading_match:
            flush_paragraph()
            level = len(heading_match.group(1))
            content = heading_match.group(2).strip()
            blocks.append((f"heading{level}", content))
            continue

        bullet_match = re.match(r"^(?:[-*•‣·]|\d+[\.)])\s+(.*)$", line)
        if bullet_match:
            flush_paragraph()
            blocks.append(("bullet", bullet_match.group(1).strip()))
            continue

        paragraph_lines.append(line)

    flush_paragraph()
    return blocks


def resume_markdown_to_pdf_bytes(text: str, title: str = "Resume") -> bytes:
    """
    Render markdown-ish resume text into PDF bytes.
    """
    body_font, bold_font, mono_font = _register_fonts()

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=title,
        author="Resume Enhancer",
    )

    styles = getSampleStyleSheet()

    base_style = ParagraphStyle(
        "BaseResumeBody",
        parent=styles["BodyText"],
        fontName=body_font,
        fontSize=10,
        leading=13,
        alignment=TA_LEFT,
        spaceAfter=6,
    )

    heading1_style = ParagraphStyle(
        "ResumeHeading1",
        parent=styles["Heading1"],
        fontName=bold_font,
        fontSize=16,
        leading=20,
        spaceBefore=10,
        spaceAfter=8,
        textColor="#111111",
    )

    heading2_style = ParagraphStyle(
        "ResumeHeading2",
        parent=styles["Heading2"],
        fontName=bold_font,
        fontSize=13,
        leading=16,
        spaceBefore=8,
        spaceAfter=6,
        textColor="#111111",
    )

    heading3_style = ParagraphStyle(
        "ResumeHeading3",
        parent=styles["Heading3"],
        fontName=bold_font,
        fontSize=11.5,
        leading=14,
        spaceBefore=6,
        spaceAfter=4,
        textColor="#111111",
    )

    bullet_style = ParagraphStyle(
        "ResumeBullet",
        parent=base_style,
        leftIndent=14,
        firstLineIndent=0,
        bulletIndent=0,
        spaceAfter=3,
    )

    story = []

    if title:
        story.append(
            Paragraph(
                _inline_markdown_to_html(title, mono_font),
                ParagraphStyle(
                    "DocumentTitle",
                    parent=styles["Title"],
                    fontName=bold_font,
                    fontSize=18,
                    leading=22,
                    spaceAfter=12,
                    textColor="#111111",
                ),
            )
        )

    blocks = _parse_blocks(text)

    for block_type, content in blocks:
        if not content and block_type == "spacer":
            story.append(Spacer(1, 0.12 * inch))
            continue

        html = _inline_markdown_to_html(content, mono_font)

        if block_type == "heading1":
            story.append(Paragraph(html, heading1_style))
        elif block_type == "heading2":
            story.append(Paragraph(html, heading2_style))
        elif block_type == "heading3":
            story.append(Paragraph(html, heading3_style))
        elif block_type == "bullet":
            story.append(Paragraph(html, bullet_style, bulletText="•"))
        else:
            story.append(Paragraph(html, base_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def text_to_pdf_bytes(text: str, title: str = "Resume") -> bytes:
    """
    Alias for resume_markdown_to_pdf_bytes.
    """
    return resume_markdown_to_pdf_bytes(text=text, title=title)


__all__ = [
    "resume_markdown_to_pdf_bytes",
    "text_to_pdf_bytes",
]
