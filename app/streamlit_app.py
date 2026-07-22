from __future__ import annotations

import os
import sys
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import streamlit as st
from openai import OpenAI

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def _env_or_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets[name]
        if isinstance(value, str):
            return value
    except Exception:
        pass
    return os.getenv(name, default)


@st.cache_resource(show_spinner=False)
def make_client(api_key: str) -> OpenAI:
    return OpenAI(base_url=GROQ_BASE_URL, api_key=api_key)


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


def _load_pipeline_modules():
    # Lazy imports so the page still loads while you are iterating on the agents.
    from agents.planner import PlanerAgent
    from agents.writer import WriterAgent
    from agents.verifier import VerifierAgent
    from agents.ats import ATSScorer
    from schemas.workflow import WorkflowState
    from tools import parser as parser_module

    return PlanerAgent, WriterAgent, VerifierAgent, ATSScorer, WorkflowState, parser_module


def _call_parser(fn, **kwargs):
    try:
        return fn(**kwargs)
    except TypeError as exc:
        # Compatibility fallback for older function signatures that do not accept `model=...`
        if "model" not in str(exc):
            raise
        kwargs.pop("model", None)
        return fn(**kwargs)


def _extract_text(source, filename: str | None):
    try:
        from tools.ocr import extract_text
    except Exception as exc:
        raise RuntimeError("OCR helper could not be loaded from `tools/ocr.py`.") from exc

    return extract_text(source, filename=filename)


def _parse_resume(parser_module, client, source, model: str):
    filename = getattr(source, "name", None)

    if hasattr(parser_module, "parse_resume_source"):
        return _call_parser(
            parser_module.parse_resume_source,
            client=client,
            source=source,
            filename=filename,
            model=model,
        )

    if hasattr(parser_module, "parse_resume_text"):
        text = _extract_text(source, filename)
        return _call_parser(
            parser_module.parse_resume_text,
            client=client,
            text=text,
            model=model,
        )

    raise AttributeError(
        "No supported resume parser found. Expected `parse_resume_source` "
        "or `parse_resume_text` in `tools/parser.py`."
    )


def _parse_job(parser_module, client, source, model: str):
    filename = getattr(source, "name", None)

    if hasattr(parser_module, "parse_job_source"):
        return _call_parser(
            parser_module.parse_job_source,
            client=client,
            source=source,
            filename=filename,
            model=model,
        )

    if hasattr(parser_module, "parse_job_text"):
        text = _extract_text(source, filename)
        return _call_parser(
            parser_module.parse_job_text,
            client=client,
            text=text,
            model=model,
        )

    raise AttributeError(
        "No supported job parser found. Expected `parse_job_source` "
        "or `parse_job_text` in `tools/parser.py`."
    )


def run_pipeline(client: OpenAI, resume_file, job_file, model: str):
    try:
        PlanerAgent, WriterAgent, VerifierAgent, ATSScorer, WorkflowState, parser_module = _load_pipeline_modules()
    except Exception as exc:
        raise RuntimeError(
            "Failed to load the pipeline modules.\n\n"
            "Make sure:\n"
            "- `prompts/prompts.py` defines `WRITER_PROMPT` and `ATS_PROMPT`\n"
            "- `tools/parser.py` exposes the LLM-backed parser helpers\n"
            "- `tools/ocr.py` does not have the `PDF_EXTENSIONS` typo if you're parsing PDFs\n"
        ) from exc

    try:
        resume_file.seek(0)
    except Exception:
        pass

    try:
        job_file.seek(0)
    except Exception:
        pass

    resume = _parse_resume(parser_module, client, resume_file, model=model)
    job = _parse_job(parser_module, client, job_file, model=model)

    state = WorkflowState(resume=resume, job=job)

    # Linear prototype pipeline
    pipeline = [
        PlanerAgent(client=client, model=model),
        WriterAgent(client=client, model=model),
        VerifierAgent(client=client, model=model),
        ATSScorer(client=client, model=model),
    ]

    for agent in pipeline:
        name = agent.__class__.__name__
        state.logs.append(f"Starting {name}...")
        state = agent.run(state)
        state.logs.append(f"Finished {name}!")

    return state


def _render_metrics(state):
    plan_count = len(state.plan.tasks) if state.plan else 0
    verification = state.analysis.get("verification") or {}
    ats = state.analysis.get("ats_score") or {}
    score = ats.get("score")
    passed = verification.get("passed")

    cols = st.columns(3)
    cols[0].metric("Plan tasks", plan_count)
    cols[1].metric("ATS score", score if isinstance(score, (int, float)) else "—")
    if passed is True:
        cols[2].metric("Verification", "Passed")
    elif passed is False:
        cols[2].metric("Verification", "Failed")
    else:
        cols[2].metric("Verification", "—")


def _render_state(state):
    _render_metrics(state)
    st.divider()

    st.subheader("Parsed Resume")
    with st.expander("Show parsed resume JSON", expanded=False):
        st.json(_jsonable(state.resume))

    st.subheader("Parsed Job")
    with st.expander("Show parsed job JSON", expanded=False):
        st.json(_jsonable(state.job))

    st.subheader("Plan")
    if state.plan and state.plan.tasks:
        for i, task in enumerate(state.plan.tasks, 1):
            with st.expander(f"Task {i}: {task.agent} → {task.target}", expanded=i == 1):
                st.markdown(f"**Agent:** `{task.agent}`")
                st.markdown(f"**Target:** `{task.target}`")
                st.write(task.objective)
    else:
        st.info("No plan generated yet.")

    st.subheader("Draft Resume")
    draft = state.analysis.get("draft_resume_text")
    if draft:
        st.text_area("Draft resume", value=draft, height=420)
        try:
            from tools.pdf_renderer import resume_markdown_to_pdf_bytes

            pdf_bytes = resume_markdown_to_pdf_bytes(draft, title="Resume")
            st.download_button(
                "Download PDF",
                data=pdf_bytes,
                file_name="resume.pdf",
                mime="application/pdf",
            )
        except Exception:
            st.download_button(
                "Download text",
                data=draft.encode("utf-8"),
                file_name="resume.txt",
                mime="text/plain",
            )
            st.caption("PDF renderer is not available yet, so the draft was offered as plain text.")
    else:
        st.info("No draft resume generated yet.")

    st.subheader("Verification")
    verification = state.analysis.get("verification")
    if verification:
        passed = verification.get("passed")
        issues = verification.get("issues", [])
        if passed is True:
            st.success("Verification passed")
        else:
            st.error(f"Verification failed with {len(issues)} issue(s)")
            for issue in issues:
                issue_type = issue.get("type", "issue")
                severity = issue.get("severity", "unknown")
                message = issue.get("message", "")
                st.write(f"- **{issue_type}** ({severity}): {message}")

        with st.expander("Raw verification JSON", expanded=False):
            st.json(_jsonable(verification))
    else:
        st.info("No verification result yet.")

    st.subheader("ATS")
    ats = state.analysis.get("ats_score")
    if ats:
        score = ats.get("score")
        if isinstance(score, (int, float)):
            st.metric("ATS score", score)

        if ats.get("matched_keywords"):
            st.write("**Matched keywords:**", ", ".join(map(str, ats["matched_keywords"])))
        if ats.get("missing_keywords"):
            st.write("**Missing keywords:**", ", ".join(map(str, ats["missing_keywords"])))

        with st.expander("Raw ATS JSON", expanded=False):
            st.json(_jsonable(ats))
    else:
        st.info("No ATS score yet.")

    with st.expander("Logs", expanded=False):
        st.code("\n".join(state.logs) or "No logs", language="text")


def main():
    st.set_page_config(page_title="Resume Enhancer", layout="wide")
    st.title("Resume Enhancer")
    st.write(
        "Upload a resume and a job description. The app will parse both, build a plan, "
        "rewrite the resume, verify it, and compute an ATS-style score."
    )

    with st.sidebar:
        st.header("Settings")
        api_key_input = st.text_input(
            "Groq API key",
            type="password",
            help="Leave blank to use `GROQ_API_KEY` from your environment or Streamlit secrets.",
        )
        api_key = api_key_input or _env_or_secret("GROQ_API_KEY", "")
        model = st.text_input("Model", value="llama3-70b-8192")
        st.caption("The same model is used for parsing and all agents in this linear prototype.")

    if not api_key:
        st.warning("Provide a Groq API key in the sidebar or set `GROQ_API_KEY`.")
    process_disabled = not bool(api_key)

    st.caption("Supported file types: PDF, PNG, JPG, JPEG, DOCX, TXT")

    col1, col2 = st.columns(2)
    with col1:
        resume_file = st.file_uploader(
            "Upload resume",
            type=["pdf", "png", "jpg", "jpeg", "docx", "txt"],
            key="resume_file",
        )
    with col2:
        job_file = st.file_uploader(
            "Upload job description",
            type=["pdf", "png", "jpg", "jpeg", "docx", "txt"],
            key="job_file",
        )

    if st.button("Process", type="primary", disabled=process_disabled):
        if resume_file is None or job_file is None:
            st.error("Please upload both a resume and a job description.")
        else:
            client = make_client(api_key)
            with st.spinner("Parsing files and running agents..."):
                try:
                    state = run_pipeline(client, resume_file, job_file, model=model)
                    st.session_state["workflow_state"] = state
                    st.success("Processing complete.")
                except Exception as exc:
                    st.session_state.pop("workflow_state", None)
                    st.error("Processing failed.")
                    st.exception(exc)

    state = st.session_state.get("workflow_state")
    if state:
        st.divider()
        _render_state(state)
    else:
        st.info("Upload files and click Process to run the pipeline.")


if __name__ == "__main__":
    main()
