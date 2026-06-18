import base64
import io
import json
import mimetypes
import os
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

import streamlit as st

# Make sure project root is on sys.path so we can import src modules
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Try to import the agent if available
try:
    from src.agent import run_agent  # noqa: E402

    AGENT_AVAILABLE = True
    AGENT_IMPORT_ERROR = None
except Exception:
    run_agent = None
    AGENT_AVAILABLE = False
    AGENT_IMPORT_ERROR = traceback.format_exc()


def get_openai_client():
    """Create an OpenAI client configured to talk to Groq's OpenAI-compatible endpoint.

    This uses the `openai` Python package but constructs an `openai.OpenAI`
    instance pointed at Groq's base_url. The function returns a small client
    whose `chat.completions.create(...)` method performs light normalization of
    Groq-style messages (list content with image_url parts) into plain text so
    the rest of the code can continue calling `client.chat.completions.create(...)`.

    Returns (client, error_message).
    """
    try:
        import openai
    except Exception as e:
        return None, f"openai import failed: {e}"

    # Prefer Streamlit secrets, fall back to environment variable
    api_key = None
    try:
        api_key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        api_key = None

    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")

    base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

    try:
        if api_key:
            client_actual = openai.OpenAI(base_url=base_url, api_key=api_key)
        else:
            client_actual = openai.OpenAI(base_url=base_url)
    except Exception as e:
        return None, f"failed to create OpenAI client for Groq endpoint: {e}"

    def create(
        model=None,
        messages=None,
        response_format=None,
        tools=None,
        tool_choice=None,
        **kwargs,
    ):
        # Preserve Groq-style message content when present (e.g., lists that include
        # {"type": "image_url", "image_url": ...}). If the message content is a
        # list, send it through unchanged so the Groq endpoint can handle images/PDFs.
        payload_messages = []
        for m in messages or []:
            # If the message has a content that's a list (structured parts), preserve it
            if isinstance(m.get("content"), list):
                payload_messages.append(m)
            else:
                # Otherwise, send the message unchanged
                payload_messages.append(m)

        # Call the OpenAI/Groq Chat Completion API via the client instance
        # Include response_format so upstream code can request structured JSON
        resp = client_actual.chat.completions.create(
            model=model,
            messages=payload_messages,
            response_format=response_format,
            **kwargs,
        )

        # Extract the assistant content from the response (support dict-like and object-like shapes)
        content = ""
        try:
            # dict-like
            content = resp["choices"][0]["message"]["content"]
        except Exception:
            try:
                content = resp["choices"][0]["text"]
            except Exception:
                try:
                    # object-like
                    content = resp.choices[0].message.content
                except Exception:
                    content = ""

        # If a structured json object was requested, try to parse it
        content_out = content
        if (
            response_format
            and isinstance(response_format, dict)
            and response_format.get("type") == "json_object"
        ):
            try:
                content_out = json.loads(content)
            except Exception:
                content_out = content

        # Try to preserve tool_calls from the upstream response if present
        tool_calls = None
        try:
            # dict-like
            tool_calls = resp["choices"][0]["message"].get("tool_calls")
        except Exception:
            try:
                # object-like
                tool_calls = getattr(resp.choices[0].message, "tool_calls", None)
            except Exception:
                tool_calls = None

        message_obj = SimpleNamespace(content=content_out, tool_calls=tool_calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=message_obj)])

    client = SimpleNamespace()
    client.chat = SimpleNamespace()
    client.chat.completions = SimpleNamespace(create=create)
    return client, None


def _bytes_to_text_pdf(b: bytes) -> str | None:
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(b)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
        text = "\n\n".join(pages).strip()
        return text if text else None
    except Exception:
        return None


def _bytes_to_text_docx(b: bytes) -> str | None:
    try:
        import docx

        doc = docx.Document(io.BytesIO(b))
        paragraphs = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
        text = "\n".join(paragraphs).strip()
        return text if text else None
    except Exception:
        return None


def _bytes_to_text_image_ocr(b: bytes) -> str | None:
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(b)).convert("RGB")
        text = pytesseract.image_to_string(img)
        return text.strip() if text else None
    except Exception:
        return None


def _to_data_uri(b: bytes, filename: str) -> str:
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    b64 = base64.b64encode(b).decode("ascii")
    return f"data:{mime};base64,{b64}"


MAX_INLINE_BYTES = 4 * 1024 * 1024  # 4 MB


def extract_text_from_upload(uploaded_file, client=None, prefer_structured=False):
    """Attempt to extract text from an uploaded file.

    Strategy:
    - For text-like files, decode locally.
    - For .docx/.pdf try local parsing using python-docx / pdfplumber.
    - For images, attempt pytesseract OCR if available.
    - If local extraction fails and a Groq/OpenAI client is available, send the file as a
      data URI to the `src.extracter.ImageExtractor` which will ask the model to extract text.

    Returns extracted text (string) or None on failure.
    """
    if uploaded_file is None:
        return None

    name = uploaded_file.name
    ext = Path(name).suffix.lower()
    b = uploaded_file.read()

    # Small text files
    if ext in {".txt", ".md", ".json", ".csv"}:
        try:
            return b.decode("utf-8")
        except Exception:
            try:
                return b.decode("latin-1")
            except Exception:
                return None

    # DOCX
    if ext == ".docx":
        txt = _bytes_to_text_docx(b)
        if txt:
            return txt

    # PDF (try direct text extraction first)
    if ext == ".pdf":
        txt = _bytes_to_text_pdf(b)
        if txt:
            return txt

    # Images
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp"}:
        txt = _bytes_to_text_image_ocr(b)
        if txt:
            return txt

    # If we get here, local extraction failed. Try model-based extraction if we have a client.
    if client is None:
        return None

    if len(b) > MAX_INLINE_BYTES:
        # Avoid inlining very large files into requests
        return None

    try:
        data_uri = _to_data_uri(b, name)
        # Import the image extractor lazily
        from src.extracter import ImageExtractor

        extractor = ImageExtractor()
        if prefer_structured:
            # For resumes, prefer structured JSON if the model supports it
            res = extractor.resume_extract(client, data_uri)
            # If the extractor returned a dict-like structured resume, flatten to text
            if isinstance(res, dict):
                parts = []
                for k in [
                    "name",
                    "contact",
                    "summary",
                    "experience",
                    "education",
                    "skills",
                ]:
                    if k in res and res[k]:
                        parts.append(f"{k.upper()}:\n{res[k]}\n")
                return "\n".join(parts)
            else:
                return res
        else:
            res = extractor.job_extract(client, data_uri)
            return res
    except Exception:
        return None


def main():
    st.set_page_config(page_title="ResumeFixor", page_icon="📄")
    st.title("ResumeFixor")
    st.write(
        "Upload a resume (PDF/DOCX/Images) or paste the resume text, then click Submit to run the agent."
    )

    uploaded_resume_file = st.file_uploader(
        "Upload resume (pdf, docx, png, jpg, jpeg, txt). For scanned PDFs/images the app will attempt OCR or use the model to extract text.",
        type=["pdf", "docx", "png", "jpg", "jpeg", "txt", "md", "json", "csv"],
        key="resume_uploader",
    )

    uploaded_job_file = st.file_uploader(
        "Upload job description (pdf, docx, png, jpg, jpeg, txt) (optional)",
        type=["pdf", "docx", "png", "jpg", "jpeg", "txt", "md", "json", "csv"],
        key="job_uploader",
    )

    pasted_resume = st.text_area("Or paste your resume text here", height=200)
    pasted_job = st.text_area(
        "Or paste job description text here (optional)", height=150
    )

    col1, col2 = st.columns(2)
    with col1:
        submit = st.button("Submit")
    with col2:
        demo_run = st.button("Run demo (no API)")

    if not AGENT_AVAILABLE:
        st.info(
            "Agent code not importable. If you want the app to call the agent, fix import errors in `src/agent.py` first."
        )
        st.caption("Import error traceback (for debugging):")
        st.text(AGENT_IMPORT_ERROR or "No import error captured")

    if submit or demo_run:
        # Initialize client if this is a real run (not a demo)
        client = None
        if not demo_run:
            client, client_err = get_openai_client()
            if client is None:
                st.error("No LLM client available: " + (client_err or "unknown error"))
                st.info(
                    "To enable the real agent, set the GROQ_API_KEY in Streamlit secrets or as an environment variable."
                )
                return

        # Determine resume and job texts (try file extraction first, then pasted text)
        status_placeholder = st.empty()

        resume_text = None
        if uploaded_resume_file is not None:
            status_placeholder.info("Extracting resume text from uploaded file...")
            resume_text = extract_text_from_upload(
                uploaded_resume_file, client, prefer_structured=True
            )
            if resume_text is None:
                st.warning(
                    "Couldn't extract text from the uploaded resume. Please paste the resume text or upload a text-based PDF/DOCX."
                )
        if not resume_text and pasted_resume:
            resume_text = pasted_resume.strip()

        job_text = None
        if uploaded_job_file is not None:
            status_placeholder.info(
                "Extracting job description text from uploaded file..."
            )
            job_text = extract_text_from_upload(
                uploaded_job_file, client, prefer_structured=False
            )
            if job_text is None:
                st.warning(
                    "Couldn't extract text from the uploaded job description. Please paste the job description text or upload a text-based PDF/DOCX."
                )
        if not job_text and pasted_job:
            job_text = pasted_job.strip()

        if not resume_text:
            st.error(
                "No resume text found. Upload a resume (PDF/DOCX/Images) or paste the resume contents."
            )
            return

        # Show a running indicator for the agent
        status_placeholder.info("The agent is running...")

        # Demo run: don't call the LLM or agent
        if demo_run:
            time.sleep(2)  # simulate work
            status_placeholder.success("Agent finished (demo)")
            st.subheader("Output (demo)")
            st.write("This was a demo run; no LLM was called.")
            st.markdown(resume_text)
            return

        if not AGENT_AVAILABLE:
            status_placeholder.error(
                "Agent implementation not available to run (import failed)."
            )
            return

        # Run the actual agent. This may take a while depending on your model and API.
        with st.spinner("Agent is running... this may take a while"):
            if run_agent is None:
                status_placeholder.error(
                    "Agent implementation not available to run (import failed)."
                )
                return
            try:
                result = run_agent(client, resume_text, job_text or "")
            except Exception as e:
                status_placeholder.error("Agent run failed: " + str(e))
                st.exception(e)
                return

        status_placeholder.success("Agent finished")
        st.subheader("Agent output")
        # run_agent should return text or structured JSON
        if isinstance(result, (dict, list)):
            st.json(result)
        else:
            st.markdown(result)


if __name__ == "__main__":
    main()
