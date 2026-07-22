from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from .job import Job
from .resume import Resume
from .plan import Plan

@dataclass
class WorkflowState:
    resume: Resume
    job: Job
    plan: Optional[Plan] = None
    analysis: dict = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)