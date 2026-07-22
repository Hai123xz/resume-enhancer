import json
import unittest
from unittest.mock import MagicMock

from agents.ats import ATSScorer
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


def build_state():
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

    return WorkflowState(resume=resume, job=job)


class TestATSScorer(unittest.TestCase):
    def test_ats_scorer_stores_score(self):
        fake_response = MagicMock()
        fake_response.choices[0].message.content = json.dumps(
            {
                "score": 82,
                "matched_keywords": ["Python", "AWS"],
                "missing_keywords": ["Docker"],
                "strengths": ["Strong backend experience"],
                "weaknesses": ["Missing Docker keyword"],
                "recommendations": ["Add Docker if truthful"],
            }
        )

        client = MagicMock()
        client.chat.completions.create.return_value = fake_response

        agent = ATSScorer(client=client)
        state = build_state()

        new_state = agent.run(state)

        self.assertIn("ats_score", new_state.analysis)
        self.assertEqual(new_state.analysis["ats_score"]["score"], 82)
        self.assertEqual(
            new_state.analysis["ats_score"]["matched_keywords"],
            ["Python", "AWS"],
        )
        self.assertIn("ATS score computed: 82", new_state.logs[-1])
        client.chat.completions.create.assert_called_once()
