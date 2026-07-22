from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from operator import contains
from typing import List, Optional

@dataclass
class ContactInfo:
    """Basic contact details"""
    full_name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None

@dataclass
class EducationEntry:
    """One education credential."""
    degree: str
    instituion: str
    start_date: str
    end_date: Optional[str] = None
    gpa: Optional[float] = None
    activities: List[str] = field(default_factory=list)

@dataclass
class ExperienceEntry:
    title: str
    company: str
    start_date: str
    end_date: Optional[str] = None
    location: Optional[str] = None
    responsibilities: List[str] = field(default_factory=list)
    achievements: List[str] = field(default_factory=list)

@dataclass
class Skill:
    """A single skill"""
    name: str
    description: Optional[str] = None
    proficiency: Optional[str] = None
    group: Optional[SkillGroup] = None

@dataclass
class SkillGroup:
    """A group of the same category skills"""
    name: str
    skills: List[Skill]

@dataclass
class ProjectEntry:
    name: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    url: Optional[str] = None

@dataclass
class Certifications:
    name: str
    date_obtained: Optional[str] = None
    
@dataclass
class Resume:
    contact: ContactInfo
    certifications: List[Certifications]
    summary: Optional[str] = None
    education: List[EducationEntry] = field(default_factory=list)
    experience: List[ExperienceEntry] = field(default_factory=list)
    skills: List[Skill] = field(default_factory=list)
    projects: Optional[List[ProjectEntry]] = None
    created_at: date = field(default_factory=date.today)
    updated_at: Optional[date] = None