from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CalendarPageCreate(BaseModel):
    brand_id: Optional[str] = None
    connection_id: Optional[str] = None
    slug: str
    title: str
    description: Optional[str] = None
    duration_minutes: int = 30
    buffer_minutes: int = 15
    working_hours_json: Optional[dict] = None
    timezone: str = "UTC"
    max_days_ahead: int = 14
    is_active: bool = True


class CalendarPageUpdate(BaseModel):
    connection_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    buffer_minutes: Optional[int] = None
    working_hours_json: Optional[dict] = None
    timezone: Optional[str] = None
    max_days_ahead: Optional[int] = None
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
    attendee_name: str
    attendee_email: str
    start_at: str
    message: Optional[str] = None


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
