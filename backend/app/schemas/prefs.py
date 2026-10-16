"""Pydantic models for user preferences and API payloads."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Climate = Literal["cold", "cool", "mild", "warm", "hot"]
Pace = Literal["relaxed", "balanced", "packed"]
Style = Literal["solo", "couple", "family", "friends"]
Tier = Literal["hostel", "budget", "homestay", "midrange", "premium"]
Mode = Literal["bus", "train", "car", "flight"]
Season = Literal["winter", "summer", "monsoon", "post-monsoon"]


class Preferences(BaseModel):
    """Structured user requirements (the single source of truth for a trip)."""
    origin: Optional[str] = None
    destination: Optional[str] = None            # chosen destination id, None = "surprise me"
    budget: Optional[float] = Field(default=None, gt=0, le=10_000_000)   # TOTAL for the whole group, INR
    duration_days: Optional[int] = Field(default=None, ge=1, le=14)
    start_date: Optional[str] = None             # ISO date
    travellers: int = Field(default=1, ge=1, le=12)
    climate: Optional[Climate] = None
    season: Optional[Season] = None
    interests: list[str] = Field(default_factory=list)
    excluded_activities: list[str] = Field(default_factory=list)      # keywords e.g. "trekking"
    excluded_destinations: list[str] = Field(default_factory=list)
    travel_style: Optional[Style] = None
    elderly: bool = False
    children: bool = False
    transport: list[Mode] = Field(default_factory=list)               # empty = any
    accommodation: Optional[Tier] = None
    dietary: list[str] = Field(default_factory=list)
    accessibility_required: bool = False
    pace: Pace = "balanced"
    randomize: bool = False
    seed: int = 0

    @field_validator("origin", "destination", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip().lower() if isinstance(v, str) and v.strip() else None

    @field_validator("interests", "excluded_activities", "excluded_destinations", "dietary", mode="before")
    @classmethod
    def _lower_list(cls, v):
        return sorted({str(x).strip().lower() for x in (v or []) if str(x).strip()})


class RecommendRequest(BaseModel):
    prefs: Preferences
    top_n: int = Field(default=10, ge=1, le=30)
    sort: Literal["match", "cost"] = "match"


class ItineraryRequest(BaseModel):
    prefs: Preferences
    destination_id: str
    transport_mode: Optional[Mode] = None
    accommodation_tier: Optional[Tier] = None
    food_tier: Optional[Literal["budget", "mid", "premium"]] = None
