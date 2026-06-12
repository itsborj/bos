from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CalendarPageCreate(BaseModel):
    brand_id: Optional[str] = None
    connection_id: Optional[str] = None
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    duration_minutes: int = Field(default=30, gt=0, le=480)
    buffer_minutes: int = Field(default=15, ge=0, le=240)
    working_hours_json: Optional[dict] = None
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    max_days_ahead: int = Field(default=14, gt=0, le=365)
    is_active: bool = True


class CalendarPageUpdate(BaseModel):
    connection_id: Optional[str] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    duration_minutes: Optional[int] = Field(default=None, gt=0, le=480)
    buffer_minutes: Optional[int] = Field(default=None, ge=0, le=240)
    working_hours_json: Optional[dict] = None
    timezone: Optional[str] = Field(default=None, min_length=1, max_length=100)
    max_days_ahead: Optional[int] = Field(default=None, gt=0, le=365)
    is_active: Optional[bool] = None


class CalendarPageResponse(BaseModel):
    id: str
    workspace_id: str
    brand_id: Optional[str]
    connection_id: Optional[str]
    slug: str
    title: str
    description: Optional[str]
    duration_minutes: int
    buffer_minutes: int
    working_hours_json: Optional[dict]
    timezone: str
    max_days_ahead: int
    is_active: bool
    embed_url: str
    created_at: datetime
    updated_at: datetime


class BookingRequest(BaseModel):
    attendee_name: str = Field(min_length=1, max_length=200)
    attendee_email: str = Field(min_length=3, max_length=320)
    start_at: str = Field(min_length=1, max_length=80)
    message: Optional[str] = Field(default=None, max_length=2000)


class BookingResponse(BaseModel):
    id: str
    attendee_name: str
    attendee_email: str
    start_at: datetime
    end_at: datetime
    status: str
    created_at: datetime


class DaySlots(BaseModel):
    date: str
    slots: list[str]


class AvailabilityResponse(BaseModel):
    slug: str
    title: str
    description: Optional[str]
    timezone: str
    duration_minutes: int
    days: list[DaySlots]
