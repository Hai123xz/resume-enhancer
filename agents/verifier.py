from openai import OpenAI
import json
from schemas.workflow import WorkflowState
from .base import BaseAgent
from prompts.prompts import VERIFIER_PROMPT
import re

class VerifierAgent(BaseAgent):
    def __init__(self, client: OpenAI, model: str = 'openai/gpt-oss-120b'):
        self.client = client
        self.model = model

    def _safe_json_loads(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1].strip()
        return json.loads(text)

    def _extract_source_facts(self, state: WorkflowState) -> dict:
        """Extract source fact for verifying"""
        resume = state.resume
        job = state.job

        companies = []
        dates = []
        technologies = set()

        for exp in resume.experience:
            companies.append(exp.company)
            dates.append(exp.start_date)
            if exp.end_date:
                dates.append(exp.end_date)
            for tech in exp.responsibilities:
                technologies.add(tech)

        for proj in (resume.projects or []):
            if getattr(proj, "url", None):
                technologies.add(proj.url)
            if getattr(proj, "name", None):
                technologies.add(proj.name)

        for skill in resume.skills:
            technologies.add(skill.name)

        for s in job.required_skills:
            technologies.add(s)
        for s in job.preferred_skills:
            technologies.add(s)

        return {
            "companies": [c for c in companies if c],
            'dates': [d for d in dates if d],
            'technologies': sorted([t for t in technologies if t])
        }

    def _deterministic_checks(self, draft: str, facts: dict) -> list[str]:
        issues = []

        # fake companies
        for company in re.findall(r"\b[A-Z][A-Za-z0-9&.\- ]{2,}\b", draft):
            if company in facts["companies"]:
                continue

        # dates like 2021, 2022, Jan 2024, etc. — simple heuristic
        date_patterns = re.findall(
            r"\b(?:\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b",
            draft,
            flags=re.IGNORECASE,
        )
        for d in date_patterns:
            if d not in facts["dates"]:
                issues.append(f"Unsupported or unverified date found: {d}")

        return issues
    
    def run(self, state : WorkflowState) -> WorkflowState:
        draft = state.analysis.get('draft_resume_text')

        if not draft:
            state.logs.append("VerifierAgent skipped: no draft_resume_text found")
            return state
        facts = self._extract_source_facts(state)
        deterministic_issues = self._deterministic_checks(draft, facts)
        user_prompt = f"""
        SOURCE FACTS: {json.dumps(facts, indent=2)}
        DRAFT RESUME: {draft}"""

        response = self.client.chat.completions.create(
            model = self.model,
            messages=[
                {"role" : "system", "content": VERIFIER_PROMPT},
                {"role": 'user', 'content': user_prompt}
            ],
            temperature=0.0,
        )

        content = response.choices[0].message.content
        result = self._safe_json_loads(content)
        issues = result.get("issues", [])

        for issue in deterministic_issues:
            issues.append(
                {
                    "type": "date",
                    "severity": 'high',
                    'message': issue,
                    'evidence': ''
                }
            )
        passed = len(issues) == 0
        state.analysis['verification'] = {
            "passed": passed,
            'issues': issues
        }

        if passed:
            state.logs.append("Verification passed")
        else:
            state.logs.append(f"Verification failed with {len(issues)} issue(s)")
        return state
        