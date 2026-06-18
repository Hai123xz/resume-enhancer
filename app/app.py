import base64

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
from PIL import Image

client = OpenAI(
    base_url="https://api.groq.com/openai/v1", api_key=os.environ.get("GROQ_API_KEY")
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
            image = Image.open(uploaded_file)
            st.image(image, caption=filename, use_column_width=True)
        except Exception as e:
            st.error(f"Could not display image: {e}")

    elif file_ext == "pdf":
        try:
            # Read the PDF bytes and embed as base64 in an iframe for preview
            pdf_bytes = uploaded_file.read()
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

# Add process streamlit


def process_files(resume_file, jd_file):
    """Placeholder processing function.

    Replace the body of this function with the real processing you want to run
    (parsing PDFs, calling an API, comparing skills, etc.). It should accept
    the uploaded file-like objects returned by the file_uploader widgets.
    """
    # Basic validation
    if resume_file is None and jd_file is None:
        return "No files provided"

    results = []

    if resume_file is not None:
        results.append(
            f"Resume: {resume_file.name} ({len(resume_file.getvalue()) if hasattr(resume_file, 'getvalue') else 'size unknown'} bytes)"
        )
    if jd_file is not None:
        results.append(
            f"Job description: {jd_file.name} ({len(jd_file.getvalue()) if hasattr(jd_file, 'getvalue') else 'size unknown'} bytes)"
        )

    # Example result (replace with actual logic)
    return "\n".join(results)


# Place the button below the uploaders and call `process_files` when clicked
if st.button("Process"):
    with st.spinner("Processing files..."):
        try:
            output = process_files(resume, jd)
            st.success("Processing complete")
            st.text_area("Output", value=output, height=200)
        except Exception as e:
            st.error(f"Processing failed: {e}")

# End of process streamlit
