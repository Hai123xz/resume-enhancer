import json
import unittest
from unittest.mock import MagicMock, patch

from tools.parser import parse_resume_text, parse_job_text, parse_resume_source


class TestParser(unittest.TestCase):
    def test_parse_resume_text(self):
        fake_response = MagicMock()
        fake_response.choices[0].message.content = json.dumps(
            {
                "contact": {
                    "full_name": "Jane Doe",
                    "email": "jane@example.com",
                    "phone": "+1 555 123 4567",
                    "location": "New York, NY",
                    "linkedin": "https://linkedin.com/in/janedoe",
                    "github": "https://github.com/janedoe",
                },
                "certifications": [
                    {
                        "name": "AWS Certified Developer",
                        "date_obtained": "2023",
                    }
                ],
                "summary": "Backend engineer with Python experience.",
                "education": [
                    {
                        "degree": "BSc Computer Science",
                        "instituion": "Test University",
                        "start_date": "2018",
                        "end_date": "2022",
                        "gpa": 3.8,
                        "activities": ["Coding club"],
                    }
                ],
                "experience": [
                    {
                        "title": "Software Engineer",
                        "company": "Acme",
                        "start_date": "2021",
                        "end_date": "2024",
                        "location": "Remote",
                        "responsibilities": ["Built APIs"],
                        "achievements": ["Reduced latency by 30%"],
                    }
                ],
                "skills": [
                    {
                        "name": "Python",
                        "description": None,
                        "proficiency": "Advanced",
                    }
                ],
                "projects": [
                    {
                        "name": "Resume Enhancer",
                        "description": "AI resume tool",
                        "start_date": "2024",
                        "end_date": None,
                        "url": "https://github.com/janedoe/resume-enhancer",
                    }
                ],
            }
        )

        client = MagicMock()
        client.chat.completions.create.return_value = fake_response

        text = "Jane Doe resume text"
        resume = parse_resume_text(client=client, text=text)

        self.assertEqual(resume.contact.full_name, "Jane Doe")
        self.assertEqual(resume.contact.email, "jane@example.com")
        self.assertEqual(resume.summary, "Backend engineer with Python experience.")
        self.assertEqual(len(resume.education), 1)
        self.assertEqual(resume.education[0].degree, "BSc Computer Science")
        self.assertEqual(len(resume.experience), 1)
        self.assertEqual(resume.experience[0].company, "Acme")
        self.assertEqual(len(resume.skills), 1)
        self.assertEqual(resume.skills[0].name, "Python")
        self.assertEqual(len(resume.certifications), 1)
        self.assertEqual(resume.certifications[0].name, "AWS Certified Developer")

        client.chat.completions.create.assert_called_once()

    def test_parse_job_text(self):
        fake_response = MagicMock()
        fake_response.choices[0].message.content = json.dumps(
            {
                "title": "Backend Engineer",
                "company": "Acme",
                "summary": "Looking for a backend engineer.",
                "responsibilities": ["Build APIs", "Work with stakeholders"],
                "required_skills": ["Python", "FastAPI"],
                "preferred_skills": ["AWS"],
                "qualifications": ["3+ years experience"],
            }
        )

        client = MagicMock()
        client.chat.completions.create.return_value = fake_response

        text = "Backend Engineer job text"
        job = parse_job_text(client=client, text=text)

        self.assertEqual(job.title, "Backend Engineer")
        self.assertEqual(job.company, "Acme")
        self.assertEqual(job.summary, "Looking for a backend engineer.")
        self.assertEqual(job.required_skills, ["Python", "FastAPI"])
        self.assertEqual(job.preferred_skills, ["AWS"])
        self.assertEqual(job.qualifications, ["3+ years experience"])

        client.chat.completions.create.assert_called_once()

    @patch("tools.parser.extract_text")
    def test_parse_resume_source_calls_extract_text(self, mock_extract_text):
        fake_response = MagicMock()
        fake_response.choices[0].message.content = json.dumps(
            {
                "contact": {
                    "full_name": "Jane Doe",
                    "email": "jane@example.com",
                    "phone": None,
                    "location": None,
                    "linkedin": None,
                    "github": None,
                },
                "certifications": [],
                "summary": None,
                "education": [],
                "experience": [],
                "skills": [],
                "projects": [],
            }
        )

        client = MagicMock()
        client.chat.completions.create.return_value = fake_response
        mock_extract_text.return_value = "dummy extracted resume text"

        resume = parse_resume_source(
            client=client,
            source="fake.pdf",
            filename="fake.pdf",
        )

        self.assertEqual(resume.contact.full_name, "Jane Doe")
        mock_extract_text.assert_called_once_with(
            "fake.pdf",
            filename="fake.pdf",
            language="eng",
        )
        client.chat.completions.create.assert_called_once()
        @patch("tools.parser.extract_text")
        def test_parse_job_source_calls_extract_text(self, mock_extract_text):
            fake_response = MagicMock()
            fake_response.choices[0].message.content = json.dumps(
                {
                    "title": "Backend Engineer",
                    "company": "Acme",
                    "summary": "Looking for a backend engineer.",
                    "responsibilities": [],
                    "required_skills": ["Python"],
                    "preferred_skills": [],
                    "qualifications": [],
                }
            )
    
            client = MagicMock()
            client.chat.completions.create.return_value = fake_response
            mock_extract_text.return_value = "dummy extracted job text"
    
            from tools.parser import parse_job_source
    
            job = parse_job_source(
                client=client,
                source="job.pdf",
                filename="job.pdf",
            )
    
            self.assertEqual(job.title, "Backend Engineer")
            mock_extract_text.assert_called_once_with(
                "job.pdf",
                filename="job.pdf",
                language="eng",
            )
