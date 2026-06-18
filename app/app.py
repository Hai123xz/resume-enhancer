import base64
import os
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.extracter import ImageExtractor
from src.agent import run_agent
from src.pdf_generator import resume_markdown_to_pdf_bytes

client = OpenAI(
    base_url="https://api.groq.com/openai/v1", api_key=os.environ["GROQ_API_KEY"]
)

st.set_page_config(page_title="Resume & JD Uploader", layout="centered")
st.title("Resume & Job Description Uploader")

st.write(
    "Upload your resume and the job description. Supported formats: PDF, PNG, JPG, JPEG."
)


def show_file_preview(uploaded_file):
    """Display a preview for an uploaded PDF or image file."""
    if uploaded_file is None:
        return

    filename = uploaded_file.name
    st.write("Filename:", filename)
    file_ext = filename.split(".")[-1].lower()

    if file_ext in ("png", "jpg", "jpeg"):
        try:
            uploaded_file.seek(0)
            image = Image.open(uploaded_file)
            st.image(image, caption=filename, use_column_width=True)
            uploaded_file.seek(0)
        except Exception as e:
            st.error(f"Could not display image: {e}")

    elif file_ext == "pdf":
        try:
            # Read the PDF bytes and embed as base64 in an iframe for preview
            uploaded_file.seek(0)
            pdf_bytes = uploaded_file.read()
            uploaded_file.seek(0)
            if not pdf_bytes:
                st.error("Uploaded PDF is empty")
                return
            b64 = base64.b64encode(pdf_bytes).decode("utf-8")
            pdf_display = f'<iframe src="data:application/pdf;base64,{b64}" width="700" height="1000" type="application/pdf"></iframe>'
            components.html(pdf_display, width=700, height=1000)
            st.download_button("Download PDF", data=pdf_bytes, file_name=filename)
        except Exception as e:
            st.error(f"Could not display PDF: {e}")

    else:
        st.write("Unsupported file type")


col1, col2 = st.columns(2)

with col1:
    resume = st.file_uploader(
        "Upload your resume (PDF or image)",
        type=["pdf", "png", "jpg", "jpeg"],
        key="resume",
    )
    show_file_preview(resume)

with col2:
    jd = st.file_uploader(
        "Upload the job description (PDF or image)",
        type=["pdf", "png", "jpg", "jpeg"],
        key="jd",
    )
    show_file_preview(jd)

def process_files(resume_file, jd_file):
    resume_file.seek(0)
    jd_file.seek(0)

    resume_name = resume_file.name.lower()
    jd_name = jd_file.name.lower()
    extracter = ImageExtractor()

    # Vision-first flow: images go directly to the vision model as data URLs.
    # PDFs use embedded text when available, and scanned pages fall back to vision.
    resume_ext = resume_name.rsplit(".", 1)[-1]
    jd_ext = jd_name.rsplit(".", 1)[-1]

    if resume_ext in ("png", "jpg", "jpeg"):
        resume_data_url = extracter._file_to_data_url(resume_file)
        resume_text = extracter.resume_extract(client, resume_data_url)
    elif resume_ext == "pdf":
        resume_text = extracter._pdf_to_text(
            resume_file, client=client, document_type="resume"
        )
    else:
        raise ValueError("Unsupported resume file type")

    if jd_ext in ("png", "jpg", "jpeg"):
        jd_data_url = extracter._file_to_data_url(jd_file)
        jd_text = extracter.job_extract(client, jd_data_url)
    elif jd_ext == "pdf":
        jd_text = extracter._pdf_to_text(
            jd_file, client=client, document_type="job description"
        )
    else:
        raise ValueError("Unsupported job description file type")

    result = run_agent(client, resume_text, jd_text)
    return result

# Place the button below the uploaders and call `process_files` when clicked
if st.button("Process"):
    with st.spinner("Processing files..."):
        try:
            output = process_files(resume, jd)
            pdf_bytes = resume_markdown_to_pdf_bytes(output)
            st.success("Processing complete")
            st.text_area("Output", value=output, height=200)
            st.download_button(
                "Download Harvard Resume PDF",
                data=pdf_bytes,
                file_name="harvard_resume.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.error(f"Processing failed: {e}")
# End of process streamlit
