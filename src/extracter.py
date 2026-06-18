# Extract text from images
# The app provides an OpenAI-compatible client; this module expects a client to be
# passed into the methods (it no longer requires the `groq` SDK to be importable
# at module import time).
from config.config_file import IMAGE_MODEL_NAME


class ImageExtractor:
    def __init__(self, model_name=MODEL_NAME):
        self.model_name = model_name

    def resume_extract(self, client, image_path):
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract this resume into JSON with keys: name, contact, summary, experience[{title,company,dates,bullets}], education, skills. Keep original wording.",
                        },
                        {"type": "image_url", "image_url": image_path},
                    ],
                }
            ],
            response_format={"type": "json_object"},
        )

        return response.choices[0].message.content

    def job_extract(self, client, image_path):
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract text from this image"},
                        {"type": "image_url", "image_url": image_path},
                    ],
                }
            ],
            response_format=None,
        )

        return response.choices[0].message.content
