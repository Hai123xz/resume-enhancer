import json
import unittest
from unittest.mock import MagicMock

from agents.verifier import VerifierAgent
from schemas.workflow import WorkflowState
from schemas.resume import (
    Resume,
    ContactInfo,
    EducationEntry,
    ExperienceEntry,
    Skill,
    Certifications,
)
from schemas.job import Job


def build_state(draft_text=None):
    resume = Resume(
        contact=ContactInfo(
            full_name="Jane Doe",
            email="jane@example.com",
        ),
        certifications=[Certifications(name="AWS Certified Developer")],
        summary="Backend engineer with Python experience.",
        education=[
            EducationEntry(
                degree="BSc Computer Science",
                instituion="Test University",
                start_date="2018",
            )
        ],
        experience=[
            ExperienceEntry(
                title="Software Engineer",
                company="Acme",
                start_date="2021",
                end_date="2024",
                responsibilities=["Built APIs"],
                achievements=["Reduced latency by 30%"],
            )
        ],
        skills=[Skill(name="Python"), Skill(name="FastAPI")],
        projects=[],
    )

    job = Job(
        title="Backend Engineer",
        summary="Looking for Python backend engineers",
        required_skills=["Python", "APIs"],
        preferred_skills=["AWS"],
        qualifications=["3+ years experience"],
    )

    state = WorkflowState(resume=resume, job=job)
    if draft_text is not None:
        state.analysis["draft_resume_text"] = draft_text

    return state


class TestVerifierAgent(unittest.TestCase):
    def test_verifier_marks_passed_when_llm_returns_no_issues(self):
        fake_response = MagicMock()
        fake_response.choices[0].message.content = json.dumps(
            {
                "issues": []
            }
        )

        client = MagicMock()
        client.chat.completions.create.return_value = fake_response

        agent = VerifierAgent(client=client)
        state = build_state(
            draft_text="""
            Jane Doe
            Software Engineer at Acme from 2021 to 2024
            Built APIs using Python and FastAPI
            """
        )

        new_state = agent.run(state)

        self.assertIn("verification", new_state.analysis)
        self.assertTrue(new_state.analysis["verification"]["passed"])
        self.assertEqual(new_state.analysis["verification"]["issues"], [])
        self.assertIn("Verification passed", new_state.logs[-1])
        client.chat.completions.create.assert_called_once()

    def test_verifier_skips_when_no_draft_exists(self):
        client = MagicMock()
        agent = VerifierAgent(client=client)
        state = build_state(draft_text=None)

        new_state = agent.run(state)

        self.assertNotIn("verification", new_state.analysis)
        self.assertIn("VerifierAgent skipped", new_state.logs[-1])
        client.chat.completions.create.assert_not_called()

    def test_verifier_adds_deterministic_date_issue(self):
        fake_response = MagicMock()
        fake_response.choices[0].message.content = json.dumps({"issues": []})

        client = MagicMock()
        client.chat.completions.create.return_value = fake_response

        agent = VerifierAgent(client=client)
        state = build_state(
            draft_text="""
            Jane Doe
            Worked at Acme in 2020
            """
        )

        new_state = agent.run(state)

        self.assertIn("verification", new_state.analysis)
        self.assertFalse(new_state.analysis["verification"]["passed"])
        self.assertGreaterEqual(len(new_state.analysis["verification"]["issues"]), 1)
        self.assertIn("Verification failed", new_state.logs[-1])

    def test_verifier_detects_false_information(self):
        fake_response = MagicMock()
        fake_response.choices[0].message.content = json.dumps(
            {
                "issues": [
                    {
                        "type": "company",
                        "severity": "high",
                        "message": "The draft mentions a company that is not present in the source resume.",
                        "evidence": "Worked at GoogleX",
                    },
                    {
                        "type": "technology",
                        "severity": "high",
                        "message": "The draft mentions a technology not supported by the source facts.",
                        "evidence": "Used Rust extensively",
                    },
                    {
                        "type": "achievement",
                        "severity": "high",
                        "message": "The draft contains an unsupported achievement.",
                        "evidence": "Increased revenue by 500%",
                    },
                ]
            }
        )
    
        client = MagicMock()
        client.chat.completions.create.return_value = fake_response
    
        agent = VerifierAgent(client=client)
    
        state = build_state(
            draft_text="""
            Jane Doe
            Software Engineer at GoogleX from 2021 to 2024
            Used Rust extensively to build backend systems
            Increased revenue by 500%
            """
        )
    
        new_state = agent.run(state)
    
        self.assertIn("verification", new_state.analysis)
        self.assertFalse(new_state.analysis["verification"]["passed"])
        self.assertEqual(len(new_state.analysis["verification"]["issues"]), 3)
        self.assertEqual(new_state.analysis["verification"]["issues"][0]["type"], "company")
        self.assertEqual(new_state.analysis["verification"]["issues"][1]["type"], "technology")
        self.assertEqual(new_state.analysis["verification"]["issues"][2]["type"], "achievement")
        self.assertIn("Verification failed", new_state.logs[-1])
        client.chat.completions.create.assert_called_once()