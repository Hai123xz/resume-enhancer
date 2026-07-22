from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Job:
    title: str
    company: Optional[str] = None
    summary: Optional[str] = None
    responsibilities: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    qualifications: List[str] = field(default_factory=list)