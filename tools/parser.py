from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from openai import OpenAI

from prompts.prompts import PARSER_JOB_PROMPT, PARSER_RESUME_PROMPT
from schemas.job import Job
from schemas.resume import (
    Certifications,
    ContactInfo,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
    Resume,
    Skill,
)
from tools.ocr import extract_text


def _safe_json_loads(text: str) -> dict[str, Any]:
    text = text.strip()

    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].strip()

    return json.loads(text)


def _to_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = _to_str(value)
    return text or None


def _to_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        # try to split common delimiter-separated text
        if "\n" in text:
            return [line.strip() for line in text.splitlines() if line.strip()]
        if "," in text:
            return [item.strip() for item in text.split(",") if item.strip()]
        return [text]
    return [value]


def _build_resume(data: dict[str, Any]) -> Resume:
    contact_data = data.get("contact", {}) or {}
    contact = ContactInfo(
        full_name=_to_str(contact_data.get("full_name")),
        email=_to_str(contact_data.get("email")),
        phone=_to_optional_str(contact_data.get("phone")),
        location=_to_optional_str(contact_data.get("location")),
        linkedin=_to_optional_str(contact_data.get("linkedin")),
        github=_to_optional_str(contact_data.get("github")),
    )

    certifications = [
        Certifications(
            name=_to_str(item.get("name")),
            date_obtained=_to_optional_str(item.get("date_obtained")),
        )
        for item in _to_list(data.get("certifications"))
        if isinstance(item, dict)
    ]

    education = [
        EducationEntry(
            degree=_to_str(item.get("degree")),
            instituion=_to_str(item.get("instituion")),
            start_date=_to_str(item.get("start_date")),
            end_date=_to_optional_str(item.get("end_date")),
            gpa=_to_optional_float(item.get("gpa")),
            activities=[_to_str(x) for x in _to_list(item.get("activities")) if _to_str(x)],
        )
        for item in _to_list(data.get("education"))
        if isinstance(item, dict)
    ]

    experience = [
        ExperienceEntry(
            title=_to_str(item.get("title")),
            company=_to_str(item.get("company")),
            start_date=_to_str(item.get("start_date")),
            end_date=_to_optional_str(item.get("end_date")),
            location=_to_optional_str(item.get("location")),
            responsibilities=[
                _to_str(x) for x in _to_list(item.get("responsibilities")) if _to_str(x)
            ],
            achievements=[
                _to_str(x) for x in _to_list(item.get("achievements")) if _to_str(x)
            ],
        )
        for item in _to_list(data.get("experience"))
        if isinstance(item, dict)
    ]

    skills = [
        Skill(
            name=_to_str(item.get("name")),
            description=_to_optional_str(item.get("description")),
            proficiency=_to_optional_str(item.get("proficiency")),
        )
        for item in _to_list(data.get("skills"))
        if isinstance(item, dict)
    ]

    projects = [
        ProjectEntry(
            name=_to_str(item.get("name")),
            description=_to_optional_str(item.get("description")),
            start_date=_to_optional_str(item.get("start_date")),
            end_date=_to_optional_str(item.get("end_date")),
            url=_to_optional_str(item.get("url")),
        )
        for item in _to_list(data.get("projects"))
        if isinstance(item, dict)
    ]

    summary = _to_optional_str(data.get("summary"))

    return Resume(
        contact=contact,
        certifications=certifications,
        summary=summary,
        education=education,
        experience=experience,
        skills=skills,
        projects=projects or None,
    )


def _build_job(data: dict[str, Any]) -> Job:
    return Job(
        title=_to_str(data.get("title")),
        company=_to_optional_str(data.get("company")),
        summary=_to_optional_str(data.get("summary")),
        responsibilities=[_to_str(x) for x in _to_list(data.get("responsibilities")) if _to_str(x)],
        required_skills=[_to_str(x) for x in _to_list(data.get("required_skills")) if _to_str(x)],
        preferred_skills=[_to_str(x) for x in _to_list(data.get("preferred_skills")) if _to_str(x)],
        qualifications=[_to_str(x) for x in _to_list(data.get("qualifications")) if _to_str(x)],
    )


def parse_resume_text(
    client: OpenAI,
    text: str,
    model: str = "openai/gpt-oss-120b",
) -> Resume:
    if not text or not text.strip():
        raise ValueError("Cannot parse an empty resume text")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": PARSER_RESUME_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0.0,
    )

    content = response.choices[0].message.content or ""
    data = _safe_json_loads(content)
    return _build_resume(data)


def parse_job_text(
    client: OpenAI,
    text: str,
    model: str = "openai/gpt-oss-120b",
) -> Job:
    if not text or not text.strip():
        raise ValueError("Cannot parse an empty job description text")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": PARSER_JOB_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0.0,
    )

    content = response.choices[0].message.content or ""
    data = _safe_json_loads(content)
    return _build_job(data)


def parse_resume_source(
    client: OpenAI,
    source: object,
    filename: str | None = None,
    language: str = "eng",
    model: str = "openai/gpt-oss-120b",
) -> Resume:
    text = extract_text(source, filename=filename, language=language)
    return parse_resume_text(client=client, text=text, model=model)


def parse_job_source(
    client: OpenAI,
    source: object,
    filename: str | None = None,
    language: str = "eng",
    model: str = "openai/gpt-oss-120b",
) -> Job:
    text = extract_text(source, filename=filename, language=language)
    return parse_job_text(client=client, text=text, model=model)
