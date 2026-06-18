import html
import io
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer


SECTION_NAMES = {
    "career objective",
    "objective",
    "summary",
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
    "muc tieu nghe nghiep",
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
    Register embedded Unicode fonts.

    The black boxes came from unsupported glyphs and special Unicode punctuation.
    These font families support Vietnamese on Streamlit Cloud and local Windows.
    """
    candidates = [
        {
            "family": "ResumeSerif",
            "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "italic": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
            "bold_italic": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf",
        },
        {
            "family": "ResumeSans",
            "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "italic": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "bold_italic": "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        },
        {
            "family": "ResumeTimes",
            "regular": "C:/Windows/Fonts/times.ttf",
            "bold": "C:/Windows/Fonts/timesbd.ttf",
            "italic": "C:/Windows/Fonts/timesi.ttf",
            "bold_italic": "C:/Windows/Fonts/timesbi.ttf",
        },
        {
            "family": "ResumeArial",
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
        variants = {
            "regular": (family, regular_path),
            "bold": (f"{family}-Bold", Path(candidate["bold"])),
            "italic": (f"{family}-Italic", Path(candidate["italic"])),
            "bold_italic": (f"{family}-BoldItalic", Path(candidate["bold_italic"])),
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
        "regular": "Times-Roman",
        "bold": "Times-Bold",
        "italic": "Times-Italic",
        "bold_italic": "Times-BoldItalic",
        "family": "Times-Roman",
    }


def _normalize_text(text: str) -> str:
    """Normalize troublesome text before it reaches ReportLab."""
    text = unicodedata.normalize("NFC", text)
    replacements = {
        "\u00a0": " ",
        "\u00ad": "",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\ufeff": "",
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\ufffd": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # If an extracted resume already contains black-square placeholders, remove
    # spacing artifacts and treat word-internal squares as hyphens.
    text = re.sub(r"(?<=\w)[\u25a0\u25a1\u25aa\u25ab](?=\w)", "-", text)
    text = re.sub(r"[\u25a0\u25a1\u25aa\u25ab]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _ascii_key(text: str) -> str:
    text = _normalize_text(text)
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return text.lower().strip()


def _clean_line(line: str) -> str:
    line = _normalize_text(line)
    line = re.sub(r"^#{1,6}\s*", "", line)
    line = re.sub(r"^\*\*(.+)\*\*$", r"\1", line)
    return line.strip()


def _inline_markup(text: str) -> str:
    text = html.escape(_normalize_text(text))
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    return text


def _is_section_header(line: str) -> bool:
    clean = _ascii_key(_clean_line(line).rstrip(":"))
    return clean in SECTION_NAMES


def _split_resume_lines(resume_text: str):
    resume_text = _normalize_text(resume_text)
    return [_clean_line(line) for line in resume_text.splitlines() if line.strip()]


def _looks_like_contact(line: str) -> bool:
    lower = line.lower()
    return any(token in lower for token in ("@", "phone", "github", "linkedin", "http"))


def _build_styles():
    font = _register_resume_fonts()
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ResumeName",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontName=font["bold"],
            fontSize=14,
            leading=16,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Subtitle",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontName=font["regular"],
            fontSize=9.3,
            leading=11,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Contact",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontName=font["regular"],
            fontSize=8.4,
            leading=10,
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Normal"],
            alignment=TA_LEFT,
            fontName=font["bold"],
            fontSize=9.8,
            leading=11.5,
            textColor=colors.black,
            spaceBefore=8,
            spaceAfter=1.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["Normal"],
            fontName=font["regular"],
            fontSize=8.4,
            leading=10.2,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyBold",
            parent=styles["Body"],
            fontName=font["bold"],
            spaceBefore=2,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ResumeBullet",
            parent=styles["Body"],
            leftIndent=11,
            firstLineIndent=0,
            bulletIndent=3,
            bulletFontName=font["regular"],
            bulletFontSize=6.5,
            spaceAfter=1.5,
        )
    )
    return styles


def _add_section_header(story, styles, title: str):
    story.append(Paragraph(_normalize_text(title).upper(), styles["Section"]))
    story.append(
        HRFlowable(
            width="100%",
            thickness=0.65,
            color=colors.black,
            spaceBefore=0,
            spaceAfter=5,
        )
    )


def _flush_bullets(story, styles, bullets):
    if not bullets:
        return

    for item in bullets:
        story.append(
            Paragraph(_inline_markup(item), styles["ResumeBullet"], bulletText="-")
        )


def resume_markdown_to_pdf_bytes(resume_text: str) -> bytes:
    """
    Render agent resume text as a Harvard-style PDF resembling the template:
    centered identity, compact serif typography, ruled section headers, and
    tight bullets suitable for technical-student resumes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.42 * inch,
        leftMargin=0.42 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.35 * inch,
        title="Optimized Resume",
    )
    styles = _build_styles()
    story = []
    lines = _split_resume_lines(resume_text)

    if not lines:
        lines = ["Optimized Resume"]

    name = lines.pop(0)
    story.append(Paragraph(_inline_markup(name), styles["ResumeName"]))

    if lines and not _looks_like_contact(lines[0]) and not _is_section_header(lines[0]):
        story.append(Paragraph(_inline_markup(lines.pop(0)), styles["Subtitle"]))

    if lines and not _is_section_header(lines[0]):
        story.append(Paragraph(_inline_markup(lines.pop(0)), styles["Contact"]))

    bullets = []
    for line in lines:
        is_bullet = line.startswith(("-", "*", "\u2022", "\u00b7"))
        cleaned = re.sub(r"^[-*\u2022\u00b7]\s*", "", line).strip()

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
            style = styles["BodyBold"] if re.search(r"\b(20\d{2}|19\d{2})\b", line) else styles["Body"]
            story.append(Paragraph(_inline_markup(line), style))

    _flush_bullets(story, styles, bullets)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
