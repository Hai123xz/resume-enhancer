import json
from dataclasses import asdict
from openai import OpenAI
from agents.base import BaseAgent
from prompts.prompts import WRITER_PROMPT
from schemas.workflow import WorkflowState

class WriterAgent(BaseAgent):
    def __init__(self, client: OpenAI, model: str = "openai/gpt-oss-120b"):
        self.client = client
        self.model = model

    def _safe_json_loads(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1].strip()
        return json.loads(text)
            
    def run(self, state: WorkflowState) -> WorkflowState:
        resume = state.resume
        job = state.job
        plan = state.plan

        if plan is None:
            state.logs.append("WriterAgent skipped: no plan found")
            return state

        resume_info = {
            "contact": asdict(resume.contact),
            "summary": resume.summary,
            "education": [asdict(e) for e in resume.education],
            "experience": [asdict(e) for e in resume.experience],
            "skills": [asdict(s) for s in resume.skills],
            "projects": [asdict(p) for p in resume.projects] if resume.projects else [],
            "certifications": [asdict(c) for c in resume.certifications],
        }
        
        job_info = {
            "title": job.title,
            "company": job.company,
            "summary": job.summary,
            "responsibilities": job.responsibilities,
            "required_skills": job.required_skills,
            "preferred_skills": job.preferred_skills,
            "qualifications": job.qualifications,
        }

        plan_info = {
            "tasks": [asdict(task) for task in plan.tasks]
        }

        user_prompt = f"""
        RESUME: {json.dumps(resume_info, indent=2)}
        JOB DESCRPTION: {json.dumps(job_info, indent=2)}
        PLAN: {json.dumps(plan_info, indent=2)}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {'role': 'system', 'content': WRITER_PROMPT},
                {'role': 'user', 'content': user_prompt}
            ],
            temperature=0.2
        )

        content = response.choices[0].message.content
        data = self._safe_json_loads(content)

        draft = data.get('draft_resume_text')
        if not draft:
            raise ValueError("WriterAgent: model did not return draft_resume_text")

        state.analysis['draft_resume_text'] = draft
        state.logs.append("Generated draft resume")
        return state
        