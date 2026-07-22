import json
import unittest
from unittest.mock import MagicMock

from agents.planner import PlanerAgent
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


class TestPlannerAgent(unittest.TestCase):
    def test_planner_generates_plan(self):
        fake_response = MagicMock()
        fake_response.choices[0].message.content = json.dumps(
            {
                "tasks": [
                    {
                        "agent": "writer",
                        "target": "summary",
                        "objective": "Rewrite summary to emphasize backend APIs and Python",
                    },
                    {
                        "agent": "keyword",
                        "target": "skills",
                        "objective": "Add ATS keywords for AWS and REST APIs",
                    },
                ]
            }
        )

        client = MagicMock()
        client.chat.completions.create.return_value = fake_response

        agent = PlanerAgent(client=client)
        state = build_state()

        new_state = agent.run(state)

        self.assertIsNotNone(new_state.plan)
        self.assertEqual(len(new_state.plan.tasks), 2)
        self.assertEqual(new_state.plan.tasks[0].agent, "writer")
        self.assertEqual(new_state.plan.tasks[0].target, "summary")
        self.assertIn("Generated plan", new_state.logs[-1])
