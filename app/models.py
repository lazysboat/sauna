"""Pydantic models for the booking marketplace.

Field names match the frontend TS types EXACTLY (camelCase) so JSON needs no
mapping anywhere — see MANAGEMENT-SYSTEM-SPEC §4 / HANDOVER §2.
"""
import secrets
from typing import Literal

from pydantic import BaseModel, Field

PriceUnit = Literal["booking", "person"]
ExperienceStatus = Literal["published", "paused"]
SessionStatus = Literal["open", "booked"]


def _id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(3)}"


class Experience(BaseModel):
    id: str = Field(default_factory=lambda: _id("exp"))
    title: str
    location: str = ""
    description: str = ""
    priceAmount: float = 0
    priceUnit: PriceUnit = "booking"
    capacity: int = 1
    durationHours: float = 2
    status: ExperienceStatus = "paused"


class Session(BaseModel):
    id: str = Field(default_factory=lambda: _id("s"))
    experienceId: str
    date: str  # "yyyy-MM-dd"
    time: str  # "HH:MM"
    status: SessionStatus = "open"
