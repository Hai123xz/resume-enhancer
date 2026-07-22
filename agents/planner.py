from pyexpat.errors import messages
from .base import BaseAgent
from schemas.plan import Plan, Task
from schemas.workflow import WorkflowState
from openai import OpenAI
import json
from dataclasses import asdict
from prompts.prompts import PLANNER_PROMPT

class PlanerAgent(BaseAgent):
    def __init__(self, client: OpenAI, model: str = 'openai/gpt-oss-120b'):
        self.client = client
        self.model = model
    
    def run(self, state: WorkflowState) -> WorkflowState:
        resume = state.resume #Take the resume
        job = state.job

        resume_infor = {
            "contact": asdict(resume.contact),
            "summary": resume.summary,
            'education': [asdict(e) for e in resume.education],
            'experience': [asdict(e) for e in resume.experience],
            'skills': [asdict(s) for s in resume.skills],
            'projects': [asdict(p) for p in resume.projects] if resume.projects else [],
            'certifications': [asdict(c) for c in resume.certifications]
        }

        job_infor = {
            "title": job.title,
            "company": job.company,
            'summary': job.summary,
            'responsibilities': job.responsibilities,
            'required_skills': job.required_skills,
            'preferred_skills': job.preferred_skills,
            "qualifications": job.qualifications
        }

        user_prompt = f"""
        Resume:
            {json.dumps(resume_infor, indent=2)}
        Job description:
            {json.dumps(job_infor, indent=2)}"""

        response = self.client.chat.completions.create(
            model = self.model,
            messages = [
                {'role': 'system', 'content': PLANNER_PROMPT},
                {'role': 'user', 'content': user_prompt}
            ],
            temperature=0.2
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        tasks = [
            Task(
                agent=t['agent'],
                target=t['target'],
                objective=t['objective']
            )
            for t in data['tasks']
        ]

        state.plan = Plan(tasks=tasks)
        state.logs.append(f"Generated plan with {len(tasks)} tasks")
        return state