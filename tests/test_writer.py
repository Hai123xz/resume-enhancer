import json
import unittest
from dataclasses import asdict
from unittest.mock import MagicMock

from agents.writer import WriterAgent
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
from schemas.plan import Plan, Task


def build_state(with_plan=True):
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

    plan = None
    if with_plan:
        plan = Plan(
            tasks=[
                Task(
                    agent="writer",
                    target="summary",
                    objective="Rewrite summary to emphasize backend APIs and Python",
                )
            ]
        )

    return WorkflowState(resume=resume, job=job, plan=plan)


class TestWriterAgent(unittest.TestCase):
    def test_writer_generates_and_stores_draft(self):
        fake_response = MagicMock()
        fake_response.choices[0].message.content = json.dumps(
            {
                "draft_resume_text": "Jane Doe\nBackend Engineer\nWorked at Acme from 2021 to 2024"
            }
        )

        client = MagicMock()
        client.chat.completions.create.return_value = fake_response

        agent = WriterAgent(client=client)
        state = build_state(with_plan=True)

        new_state = agent.run(state)

        self.assertIn("draft_resume_text", new_state.analysis)
        self.assertEqual(
            new_state.analysis["draft_resume_text"],
            "Jane Doe\nBackend Engineer\nWorked at Acme from 2021 to 2024",
        )
        self.assertIn("Generated draft resume", new_state.logs[-1])
        client.chat.completions.create.assert_called_once()

    def test_writer_skips_when_no_plan(self):
        client = MagicMock()
        agent = WriterAgent(client=client)
        state = build_state(with_plan=False)

        new_state = agent.run(state)

        self.assertNotIn("draft_resume_text", new_state.analysis)
        self.assertIn("WriterAgent skipped: no plan found", new_state.logs[-1])
        client.chat.completions.create.assert_not_called()
