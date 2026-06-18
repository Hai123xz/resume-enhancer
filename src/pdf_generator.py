import html
import io
import re
from functools import lru_cache
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


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
    "hoc van",
    "kinh nghiem",
    "kinh nghiem lam viec",
    "ky nang",
    "ky nang ky thuat",
    "du an",
    "chung chi",
    "giai thuong",
    "hoat dong",
}


@lru_cache(maxsize=1)
def _register_resume_fonts():
    """
    Register Unicode TrueType fonts for Vietnamese and other non-ASCII text.

    ReportLab's built-in Helvetica font cannot render Vietnamese accents. Streamlit
    Cloud usually has DejaVu installed, and local Windows machines usually have
    Arial, so we search those paths and embed the first available font family.
    """
    candidates = [
        {
            "family": "DejaVuSansResume",
            "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "italic": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "bold_italic": "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        },
        {
            "family": "LiberationSansResume",
            "regular": "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "bold": "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "italic": "/usr/share/fonts/truetype/liberation2/LiberationSans-Italic.ttf",
            "bold_italic": "/usr/share/fonts/truetype/liberation2/LiberationSans-BoldItalic.ttf",
        },
        {
            "family": "ArialResume",
            "regular": "C:/Windows/Fonts/arial.ttf",
            "bold": "C:/Windows/Fonts/arialbd.ttf",
            "italic": "C:/Windows/Fonts/ariali.ttf",
            "bold_italic": "C:/Windows/Fonts/arialbi.ttf",
        },
    ]

    for candidate in candidates:
        regular_path = Path(candidate["regular"])
        if not regular_path.exists():
            continue

        family = candidate["family"]
        regular_name = family
        bold_name = f"{family}-Bold"
        italic_name = f"{family}-Italic"
        bold_italic_name = f"{family}-BoldItalic"

        variants = {
            "regular": (regular_name, regular_path),
            "bold": (bold_name, Path(candidate["bold"])),
            "italic": (italic_name, Path(candidate["italic"])),
            "bold_italic": (bold_italic_name, Path(candidate["bold_italic"])),
        }

        for key, (font_name, font_path) in list(variants.items()):
            if font_path.exists():
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
            else:
                variants[key] = variants["regular"]

        addMapping(family, 0, 0, variants["regular"][0])
        addMapping(family, 1, 0, variants["bold"][0])
        addMapping(family, 0, 1, variants["italic"][0])
        addMapping(family, 1, 1, variants["bold_italic"][0])

        return {
            "regular": variants["regular"][0],
            "bold": variants["bold"][0],
            "italic": variants["italic"][0],
            "bold_italic": variants["bold_italic"][0],
            "family": family,
        }

    return {
        "regular": "Helvetica",
        "bold": "Helvetica-Bold",
        "italic": "Helvetica-Oblique",
        "bold_italic": "Helvetica-BoldOblique",
        "family": "Helvetica",
    }


def _strip_vietnamese_accents(text: str) -> str:
    replacements = {
        "áàảãạăắằẳẵặâấầẩẫậ": "a",
        "ÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬ": "A",
        "éèẻẽẹêếềểễệ": "e",
        "ÉÈẺẼẸÊẾỀỂỄỆ": "E",
        "íìỉĩị": "i",
        "ÍÌỈĨỊ": "I",
        "óòỏõọôốồổỗộơớờởỡợ": "o",
        "ÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢ": "O",
        "úùủũụưứừửữự": "u",
        "ÚÙỦŨỤƯỨỪỬỮỰ": "U",
        "ýỳỷỹỵ": "y",
        "ÝỲỶỸỴ": "Y",
        "đ": "d",
        "Đ": "D",
    }
    table = {}
    for chars, replacement in replacements.items():
        for char in chars:
            table[ord(char)] = replacement
    return text.translate(table)


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
    clean = _strip_vietnamese_accents(_clean_line(line).rstrip(":")).lower()
    return clean in SECTION_NAMES


def _split_resume_lines(resume_text: str):
    return [_clean_line(line) for line in resume_text.splitlines() if line.strip()]


def _build_styles():
    font = _register_resume_fonts()
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ResumeName",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontName=font["bold"],
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
            fontName=font["regular"],
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
            fontName=font["bold"],
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
            fontName=font["regular"],
            fontSize=9.4,
            leading=11.6,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyBold",
            parent=styles["Body"],
            fontName=font["bold"],
        )
    )
    styles.add(
        ParagraphStyle(
            name="ResumeBullet",
            parent=styles["Body"],
            leftIndent=14,
            firstLineIndent=0,
            bulletIndent=4,
            bulletFontName=font["regular"],
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
            Paragraph(_inline_markup(item), styles["ResumeBullet"], bulletText="\u2022")
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
        is_bullet = line.startswith(("-", "*", "\u2022"))
        cleaned = re.sub(r"^[-*\u2022]\s*", "", line).strip()

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
