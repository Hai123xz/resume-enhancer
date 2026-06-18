import json
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
        # Normalize incoming messages (which may be in Groq-style) into OpenAI chat format
        o_msgs = []
        for m in messages or []:
            role = m.get("role", "user")
            content = m.get("content")
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict):
                        t = part.get("type")
                        if t == "text":
                            parts.append(part.get("text", ""))
                        elif t == "image_url":
                            # The Groq/OpenAI chat model won't fetch the image; include the URL inline so the model can reason about it.
                            parts.append(f"[Image: {part.get('image_url')}]")
                        else:
                            parts.append(str(part))
                    else:
                        parts.append(str(part))
                text = "\n".join(parts)
            else:
                text = content
            o_msgs.append({"role": role, "content": text})

        # Call the OpenAI/Groq Chat Completion API via the client instance
        resp = client_actual.chat.completions.create(
            model=model, messages=o_msgs, **kwargs
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


def _read_uploaded_text(uploaded_file) -> str | None:
    if uploaded_file is None:
        return None
    name = uploaded_file.name
    ext = Path(name).suffix.lower()
    data = uploaded_file.read()

    # Plain text files
    if ext in {".txt", ".md", ".json", ".csv"}:
        try:
            return data.decode("utf-8")
        except Exception:
            try:
                return data.decode("latin-1")
            except Exception:
                return None

    # For other file types (pdf, docx, images) we don't extract text in this simple demo
    return None


def main():
    st.set_page_config(page_title="ResumeFixor", page_icon="📄")
    st.title("ResumeFixor")
    st.write(
        "Upload a resume (plain text) or paste the resume text, then click Submit to run the agent."
    )

    uploaded_file = st.file_uploader(
        "Upload resume (txt, md, json). For PDF/DOCX/Images, paste text or configure an extractor."
    )
    pasted_resume = st.text_area("Or paste your resume text here", height=200)
    job_description = st.text_area("Job description (optional)", height=150)

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
        # Determine resume text
        resume_text = None
        if uploaded_file is not None:
            resume_text = _read_uploaded_text(uploaded_file)
            if resume_text is None:
                st.warning(
                    "Uploaded file is not a plain text file that this demo can parse. Please paste the resume text instead or upload a .txt/.md/.json file."
                )
        if not resume_text and pasted_resume:
            resume_text = pasted_resume.strip()

        if not resume_text:
            st.error(
                "No resume text found. Upload a plain text file or paste the resume contents."
            )
            return

        # Show a running indicator
        status_placeholder = st.empty()
        status_placeholder.info("The agent is running...")

        # If demo_run was clicked, skip trying to call an LLM/remote client
        if demo_run:
            time.sleep(2)  # simulate work
            status_placeholder.success("Agent finished (demo)")
            st.subheader("Output (demo)")
            st.write(
                "No LLM client configured. This is a demo run that did not change the resume."
            )
            st.code(resume_text)
            return

        # Otherwise try to create a real OpenAI-based client
        client, client_err = get_openai_client()
        if client is None:
            status_placeholder.error(
                "No LLM client available: " + (client_err or "unknown error")
            )
            st.info(
                "To enable the real agent, set the GROQ_API_KEY in Streamlit secrets or as an environment variable."
            )
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
                result = run_agent(client, resume_text, job_description)
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
