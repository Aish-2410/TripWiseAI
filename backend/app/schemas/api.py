"""Request bodies for the HTTP API (validated by Pydantic)."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .prefs import Preferences


class CompareRequest(BaseModel):
    ids: list[str] = Field(min_length=2, max_length=4)
    prefs: Preferences


class ExplainRequest(BaseModel):
    destination_id: str
    prefs: Preferences


class EditRequest(BaseModel):
    plan: dict
    op: dict


class OptimizeRequest(BaseModel):
    plan: dict
    relax: bool = False


class ReplanRequest(BaseModel):
    plan: dict
    changes: dict


class PlanOnly(BaseModel):
    plan: dict


class AccommodationRequest(BaseModel):
    destination_id: str
    travellers: int = Field(default=1, ge=1, le=12)
    nights: int = Field(default=2, ge=0, le=14)
    tier: Optional[Literal["hostel", "budget", "homestay", "midrange", "premium"]] = None
    accessibility_required: bool = False
    planned_attraction_ids: list[str] = Field(default_factory=list)


class TripSave(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    plan: dict
    trip_id: Optional[str] = None
    versions: list[dict] = Field(default_factory=list)


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(min_length=1, max_length=1000)
    plan: Optional[dict] = None  # the itinerary currently open in the UI, so chat edits what the user sees


class PrefsPatch(BaseModel):
    prefs: dict[str, Any]


class WeightsUpdate(BaseModel):
    weights: dict[str, float]


class ThinksRequest(BaseModel):
    prefs: Preferences
