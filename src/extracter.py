import base64
import io
import json

import pdfplumber

try:
    from config.config_file import IMAGE_MODEL_NAME
except ImportError:
    # Deployment guard: keep Streamlit Cloud from crashing if config is stale.
    IMAGE_MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"


class ImageExtractor:
    def __init__(self, model_name=IMAGE_MODEL_NAME):
        self.model_name = model_name

    def _file_to_data_url(self, uploaded_file) -> str:
        """Convert an uploaded image file into the data URL Groq vision expects."""
        if isinstance(uploaded_file, str) and uploaded_file.startswith("data:"):
            return uploaded_file

        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        file_bytes = uploaded_file.read()

        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        filename = getattr(uploaded_file, "name", "").lower()
        extension = filename.rsplit(".", 1)[-1] if "." in filename else "png"
        mime_type = "image/jpeg" if extension in ("jpg", "jpeg") else "image/png"
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _image_bytes_to_data_url(self, image_bytes: bytes) -> str:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:image/png;base64,{encoded}"

    def _vision_text_from_data_url(self, client, data_url: str, document_type: str) -> str:
        """Use the vision model for scanned PDF pages and return only raw text."""
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Extract all readable text from this {document_type} page. "
                                'Return ONLY valid JSON as {"raw_text": "..."} with original wording.'
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        try:
            return json.loads(content).get("raw_text", "").strip()
        except json.JSONDecodeError:
            return content.strip()

    def _pdf_page_to_png_data_url(self, page) -> str:
        """Render one PDF page to PNG so scanned pages can still use vision."""
        page_image = page.to_image(resolution=200).original
        buffer = io.BytesIO()
        page_image.save(buffer, format="PNG")
        return self._image_bytes_to_data_url(buffer.getvalue())

    def _pdf_to_text(self, file, client=None, document_type: str = "document") -> str:
        """
        Extract PDF text with pdfplumber first; blank/scanned pages fall back to vision.

        This preserves the app architecture: text PDFs avoid unnecessary vision calls,
        while scanned PDFs are rendered page-by-page and read by the vision model.
        """
        if hasattr(file, "seek"):
            file.seek(0)

        with pdfplumber.open(file) as pdf:
            page_texts = []
            for page in pdf.pages:
                text = (page.extract_text() or "").strip()
                if text:
                    page_texts.append(text)
                    continue

                if client is None:
                    continue

                data_url = self._pdf_page_to_png_data_url(page)
                vision_text = self._vision_text_from_data_url(
                    client, data_url, document_type
                )
                if vision_text:
                    page_texts.append(vision_text)

        if hasattr(file, "seek"):
            file.seek(0)

        return "\n\n".join(page_texts).strip()

    def resume_extract(self, client, file_or_data_url):
        data_url = (
            file_or_data_url
            if isinstance(file_or_data_url, str) and file_or_data_url.startswith("data:")
            else self._file_to_data_url(file_or_data_url)
        )

        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract this resume from the image. Return ONLY valid JSON "
                                'with this shape: {"name": ..., "contact": ..., '
                                '"experience": [...], "education": [...], "skills": [...], '
                                '"raw_text": "..."}. Keep original wording in raw_text.'
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            response_format={"type": "json_object"},
        )

        return response.choices[0].message.content

    def job_extract(self, client, file_or_data_url):
        data_url = (
            file_or_data_url
            if isinstance(file_or_data_url, str) and file_or_data_url.startswith("data:")
            else self._file_to_data_url(file_or_data_url)
        )

        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract this job description from the image. Return ONLY "
                                'valid JSON with this shape: {"title": ..., "company": ..., '
                                '"requirements": [...], "raw_text": "..."}. Keep original '
                                "wording in raw_text."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            response_format={"type": "json_object"},
        )

        return response.choices[0].message.content
