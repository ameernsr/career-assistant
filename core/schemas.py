"""Shared data contracts. Every module reads/writes these shapes — change them only after telling the team."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Seniority = Literal["intern", "junior", "mid", "senior", "lead"]


class JobPosting(BaseModel):
    """One normalized job ad. Collectors produce it; matching consumes it."""

    id: str = Field(description="stable hash of source + source_id")
    source: str = Field(description="jobinja | jobvision | karboom | irantalent | quera | remotive")
    source_id: str
    url: str = Field(description="link to the original ad (B-06)")
    title: str
    company: Optional[str] = None
    location: Optional[str] = Field(None, description="city, normalized Persian spelling when Iranian")
    country: Optional[str] = None
    remote: Optional[bool] = None
    employment_type: Optional[str] = None
    seniority: Optional[Seniority] = None
    description: str = Field("", description="plain text, contact details stripped, max ~5000 chars")
    requirements: list[str] = Field(default_factory=list, description="raw requirement / skill phrases from the ad")
    skills: list[str] = Field(default_factory=list, description="taxonomy concept ids, filled later by matching")
    date_posted: Optional[str] = Field(None, description="ISO date YYYY-MM-DD (Gregorian)")
    salary: Optional[str] = None
    language: Literal["fa", "en", "mixed"] = "fa"
    market: Literal["iran", "remote"] = "iran"
    collected_at: str


Level = Literal["junior", "mid", "senior"]
Proficiency = Literal["none", "heard", "used", "proficient"]  # only used/proficient count as known


class ConceptClaim(BaseModel):
    concept_id: str
    proficiency: Proficiency


class UserProfile(BaseModel):
    """Module A: what the conversation LLM returns, validated against the taxonomy before use (A-04)."""

    target_role: Optional[str] = Field(None, description="taxonomy role id")
    target_level: Optional[Level] = None
    current_level: Optional[Literal["none", "junior", "mid", "senior"]] = None
    education: Optional[str] = None
    years_experience: Optional[float] = None
    claims: list[ConceptClaim] = Field(default_factory=list)
    not_known: list[str] = Field(default_factory=list, description="concept ids the user explicitly said they do not know")


class ProfileDelta(BaseModel):
    """Module A correction (A-08), e.g. «من اکسل بلد نیستم» → remove_known=['excel']."""

    add_known: list[str] = Field(default_factory=list)
    remove_known: list[str] = Field(default_factory=list)
    new_target_role: Optional[str] = None
    new_target_level: Optional[Level] = None


class Roadmap(BaseModel):
    role_id: str
    target_level: Level
    known: list[str]
    stages: list[list[str]] = Field(description="topological generations of concept ids still to learn")
    resources: dict[str, list[dict]] = Field(default_factory=dict, description="concept id → verified resources")


class ResumeProfile(BaseModel):
    """Module B (B-02): extracted from the uploaded resume. Never logged, never written to disk."""

    is_resume: bool = True
    skills: list[str] = Field(default_factory=list, description="raw skill phrases as written")
    skill_ids: list[str] = Field(default_factory=list, description="taxonomy concept ids (filled in code)")
    years_experience: Optional[float] = Field(None, description="computed in code from roles' dates")
    education: list[str] = Field(default_factory=list)
    previous_roles: list[dict] = Field(default_factory=list, description="{title, company, start, end}")
    location: Optional[str] = None
    language: Literal["fa", "en", "mixed"] = "fa"


class MatchResult(BaseModel):
    job_id: str
    score: float = Field(ge=0, le=1)
    matched_skills: list[str]
    missing_skills: list[str]
    explanation: str = ""
