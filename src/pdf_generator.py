import html
import io
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


SECTION_NAMES = {
    "education",
    "experience",
    "work experience",
    "technical experience",
    "projects",
    "skills",
    "technical skills",
    "certifications",
    "awards",
    "leadership",
    "activities",
}


def _clean_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^#{1,6}\s*", "", line)
    line = re.sub(r"^\*\*(.+)\*\*$", r"\1", line)
    return line.strip()


def _inline_markup(text: str) -> str:
    text = html.escape(text.strip())
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    return text


def _is_section_header(line: str) -> bool:
    clean = _clean_line(line).rstrip(":")
    return clean.lower() in SECTION_NAMES


def _split_resume_lines(resume_text: str):
    return [_clean_line(line) for line in resume_text.splitlines() if line.strip()]


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ResumeName",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=18,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Contact",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Normal"],
            alignment=TA_LEFT,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=colors.black,
            borderWidth=0,
            borderPadding=0,
            spaceBefore=8,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.4,
            leading=11.6,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyBold",
            parent=styles["Body"],
            fontName="Helvetica-Bold",
        )
    )
    styles.add(
        ParagraphStyle(
            name="ResumeBullet",
            parent=styles["Body"],
            leftIndent=14,
            firstLineIndent=0,
            bulletIndent=4,
            bulletFontName="Helvetica",
            bulletFontSize=7,
            spaceAfter=2,
        )
    )
    return styles


def _add_section_header(story, styles, title: str):
    story.append(Paragraph(title.upper(), styles["Section"]))
    story.append(Spacer(1, 1))


def _flush_bullets(story, styles, bullets):
    if not bullets:
        return

    for item in bullets:
        story.append(
            Paragraph(_inline_markup(item), styles["ResumeBullet"], bulletText="•")
        )


def resume_markdown_to_pdf_bytes(resume_text: str) -> bytes:
    """
    Render agent resume text as a Harvard-style PDF.

    The format is intentionally conservative for technical students: centered
    identity, one-column sections, simple headings, and dense achievement bullets.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title="Optimized Resume",
    )
    styles = _build_styles()
    story = []
    lines = _split_resume_lines(resume_text)

    if not lines:
        lines = ["Optimized Resume"]

    name = lines.pop(0)
    story.append(Paragraph(_inline_markup(name), styles["ResumeName"]))

    if lines and not _is_section_header(lines[0]):
        story.append(Paragraph(_inline_markup(lines.pop(0)), styles["Contact"]))

    bullets = []
    for line in lines:
        is_bullet = line.startswith(("-", "*", "•"))
        cleaned = re.sub(r"^[-*•]\s*", "", line).strip()

        if _is_section_header(line):
            _flush_bullets(story, styles, bullets)
            bullets = []
            _add_section_header(story, styles, cleaned.rstrip(":"))
        elif is_bullet:
            bullets.append(cleaned)
        elif re.match(r"^\*\*.+\*\*$", line):
            _flush_bullets(story, styles, bullets)
            bullets = []
            story.append(Paragraph(_inline_markup(line), styles["BodyBold"]))
        else:
            _flush_bullets(story, styles, bullets)
            bullets = []
            story.append(Paragraph(_inline_markup(line), styles["Body"]))

    _flush_bullets(story, styles, bullets)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
