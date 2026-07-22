from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Task:
    agent: str
    target: str
    objective: str

@dataclass
class Plan:
    tasks: List[Task]