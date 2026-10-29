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
