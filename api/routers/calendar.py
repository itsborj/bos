from __future__ import annotations

import base64
import email.mime.text
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from data_hygiene import contains_fuzzer_garbage, reject_fuzzer_garbage
from db import get_db
from models.calendar import CalendarBooking, CalendarPage
from routers.social import get_page_token
from routers.workspace import get_singleton
from validation import NullableUUID
from schemas.calendar import (
    AvailabilityResponse,
    BookingRequest,
    BookingResponse,
    CalendarPageCreate,
    CalendarPageResponse,
    CalendarPageUpdate,
    DaySlots,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])

_PUBLIC_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,79}$")


class JavaScriptResponse(Response):
    media_type = "application/javascript"

_DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DEFAULT_HOURS = {
    "mon": {"start": "09:00", "end": "17:00"},
    "tue": {"start": "09:00", "end": "17:00"},
    "wed": {"start": "09:00", "end": "17:00"},
    "thu": {"start": "09:00", "end": "17:00"},
    "fri": {"start": "09:00", "end": "17:00"},
}


def _tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, Exception):
        return ZoneInfo("UTC")


def _public_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": {"code": "NOT_FOUND", "message": "Booking page not found", "details": None}},
    )


def _duplicate_slug_error() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"error": {"code": "DUPLICATE_BOOKING_PAGE_SLUG", "message": "Booking page slug is ambiguous", "details": None}},
    )


async def _get_public_page(db: AsyncSession, slug: str) -> CalendarPage:
    if not _PUBLIC_SLUG_RE.fullmatch(slug or "") or contains_fuzzer_garbage(slug):
        raise _public_not_found()
    rows = (await db.execute(
        select(CalendarPage)
        .where(CalendarPage.slug == slug, CalendarPage.is_active == True)  # noqa: E712
        .order_by(CalendarPage.created_at.asc(), CalendarPage.id.asc())
        .limit(2)
    )).scalars().all()
    rows = [r for r in rows if not contains_fuzzer_garbage([r.slug, r.title, r.description])]
    if not rows:
        raise _public_not_found()
    if len(rows) > 1:
        raise _duplicate_slug_error()
    return rows[0]


async def _assert_unique_active_slug(db: AsyncSession, slug: str, *, exclude_page_id: uuid.UUID | None = None) -> None:
    q = select(CalendarPage.id).where(CalendarPage.slug == slug, CalendarPage.is_active == True)  # noqa: E712
    if exclude_page_id is not None:
        q = q.where(CalendarPage.id != exclude_page_id)
    if (await db.execute(q.limit(1))).scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "DUPLICATE_SLUG", "message": "An active booking page with this slug already exists", "details": None}},
        )


def _page_response(p: CalendarPage, api_base: str) -> CalendarPageResponse:
    return CalendarPageResponse(
        id=str(p.id),
        workspace_id=str(p.workspace_id),
        brand_id=str(p.brand_id) if p.brand_id else None,
        connection_id=str(p.connection_id) if p.connection_id else None,
        slug=p.slug,
        title=p.title,
        description=p.description,
        duration_minutes=p.duration_minutes,
        buffer_minutes=p.buffer_minutes,
        working_hours_json=p.working_hours_json,
        timezone=p.timezone,
        max_days_ahead=p.max_days_ahead,
        is_active=p.is_active,
        embed_url=f"{api_base}/calendar/book/{p.slug}",
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _slots_for_day(page: CalendarPage, day: date, existing: list[CalendarBooking], busy: list[tuple[datetime, datetime]]) -> list[str]:
    wh = page.working_hours_json or _DEFAULT_HOURS
    day_key = _DAY_NAMES[day.weekday()]
    if day_key not in wh:
        return []

    tz = _tz(page.timezone)
    h = wh[day_key]
    sh, sm = map(int, h["start"].split(":"))
    eh, em = map(int, h["end"].split(":"))

    slot_start = datetime(day.year, day.month, day.day, sh, sm, tzinfo=tz)
    day_end = datetime(day.year, day.month, day.day, eh, em, tzinfo=tz)
    duration = timedelta(minutes=page.duration_minutes)
    buf = timedelta(minutes=page.buffer_minutes)

    blocked = []
    for b in existing:
        bs = b.start_at.astimezone(tz)
        be = b.end_at.astimezone(tz)
        blocked.append((bs - buf, be + buf))
    for gs, ge in busy:
        blocked.append((gs.astimezone(tz) - buf, ge.astimezone(tz) + buf))

    slots = []
    cur = slot_start
    while cur + duration <= day_end:
        end = cur + duration
        if not any(cur < be and end > bs for bs, be in blocked):
            slots.append(cur.strftime("%H:%M"))
        cur += duration
    return slots


async def _gcal_busy(token: str, tz_name: str, t_min: datetime, t_max: datetime) -> list[tuple[datetime, datetime]]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                "https://www.googleapis.com/calendar/v3/freeBusy",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "timeMin": t_min.isoformat(),
                    "timeMax": t_max.isoformat(),
                    "timeZone": tz_name,
                    "items": [{"id": "primary"}],
                },
            )
            r.raise_for_status()
            data = r.json()
        return [
            (
                datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
                datetime.fromisoformat(b["end"].replace("Z", "+00:00")),
            )
            for b in data.get("calendars", {}).get("primary", {}).get("busy", [])
        ]
    except Exception:
        return []


async def _gcal_create(token: str, page: CalendarPage, booking: CalendarBooking) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "summary": f"{booking.attendee_name} — {page.title}",
                    "description": booking.message or "",
                    "start": {"dateTime": booking.start_at.isoformat(), "timeZone": page.timezone},
                    "end": {"dateTime": booking.end_at.isoformat(), "timeZone": page.timezone},
                    "attendees": [{"email": booking.attendee_email, "displayName": booking.attendee_name}],
                    "reminders": {"useDefault": True},
                },
            )
            r.raise_for_status()
            return r.json().get("id")
    except Exception:
        return None


async def _send_confirm(token: str, page: CalendarPage, booking: CalendarBooking) -> None:
    tz = _tz(page.timezone)
    start = booking.start_at.astimezone(tz)
    end = booking.end_at.astimezone(tz)
    time_str = f"{start.strftime('%A, %B %-d, %Y')} · {start.strftime('%-I:%M %p')}–{end.strftime('%-I:%M %p')} ({page.timezone})"
    note = f"\nYour note: {booking.message}\n" if booking.message else ""
    body = f"Hi {booking.attendee_name},\n\nYour booking is confirmed.\n\nMeeting: {page.title}\nWhen: {time_str}\nDuration: {page.duration_minutes} minutes\n{note}\nWe look forward to speaking with you.\n"
    msg = email.mime.text.MIMEText(body)
    msg["To"] = booking.attendee_email
    msg["Subject"] = f"Confirmed: {page.title}"
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            await c.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {token}"},
                json={"raw": raw},
            )
    except Exception:
        pass


# ── Authenticated: page management ────────────────────────────────────────────

@router.get("/pages", response_model=list[CalendarPageResponse], dependencies=[Depends(require_api_key)])
async def list_pages(brand_id: NullableUUID = None, db: AsyncSession = Depends(get_db), settings=Depends(get_settings)):
    ws = await get_singleton(db)
    api_base = settings.frontend_url.rstrip("/") + "/api"
    q = select(CalendarPage).where(CalendarPage.workspace_id == ws.id)
    if brand_id:
        q = q.where(CalendarPage.brand_id == brand_id)
    rows = (await db.execute(q.order_by(CalendarPage.created_at.desc()))).scalars().all()
    rows = [r for r in rows if not contains_fuzzer_garbage([r.slug, r.title, r.description])]
    return [_page_response(r, api_base) for r in rows]


@router.post("/pages", response_model=CalendarPageResponse, dependencies=[Depends(require_api_key)])
async def create_page(body: CalendarPageCreate, db: AsyncSession = Depends(get_db), settings=Depends(get_settings)):
    ws = await get_singleton(db)
    api_base = settings.frontend_url.rstrip("/") + "/api"
    reject_fuzzer_garbage(body.model_dump(), ["body"])
    if body.is_active:
        await _assert_unique_active_slug(db, body.slug)
    try:
        brand_id = uuid.UUID(body.brand_id) if body.brand_id else None
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail=[{"loc": ["body", "brand_id"], "msg": "value is not a valid UUID", "type": "uuid_parsing"}])
    try:
        connection_id = uuid.UUID(body.connection_id) if body.connection_id else None
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail=[{"loc": ["body", "connection_id"], "msg": "value is not a valid UUID", "type": "uuid_parsing"}])
    page = CalendarPage(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        brand_id=brand_id,
        connection_id=connection_id,
        slug=body.slug,
        title=body.title,
        description=body.description,
        duration_minutes=body.duration_minutes,
        buffer_minutes=body.buffer_minutes,
        working_hours_json=body.working_hours_json,
        timezone=body.timezone,
        max_days_ahead=body.max_days_ahead,
        is_active=body.is_active,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return _page_response(page, api_base)


@router.patch("/pages/{page_id}", response_model=CalendarPageResponse, dependencies=[Depends(require_api_key)], responses={404: {"description": "Page not found"}})
async def update_page(page_id: uuid.UUID, body: CalendarPageUpdate, db: AsyncSession = Depends(get_db), settings=Depends(get_settings)):
    ws = await get_singleton(db)
    api_base = settings.frontend_url.rstrip("/") + "/api"
    page = (await db.execute(
        select(CalendarPage).where(CalendarPage.id == page_id, CalendarPage.workspace_id == ws.id)
    )).scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Page not found", "details": None}})
    updates = body.model_dump(exclude_unset=True)
    reject_fuzzer_garbage(updates, ["body"])
    if updates.get("is_active") is True and not page.is_active:
        await _assert_unique_active_slug(db, page.slug, exclude_page_id=page.id)
    for field, value in updates.items():
        if field == "connection_id" and value:
            try:
                value = uuid.UUID(value)
            except (ValueError, AttributeError):
                raise HTTPException(status_code=422, detail=[{"loc": ["body", "connection_id"], "msg": "value is not a valid UUID", "type": "uuid_parsing"}])
        setattr(page, field, value)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["body"], "msg": "Invalid page data", "type": "value_error"}],
        )
    await db.refresh(page)
    return _page_response(page, api_base)


@router.delete("/pages/{page_id}", dependencies=[Depends(require_api_key)], responses={404: {"description": "Page not found"}})
async def delete_page(page_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ws = await get_singleton(db)
    page = (await db.execute(
        select(CalendarPage).where(CalendarPage.id == page_id, CalendarPage.workspace_id == ws.id)
    )).scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Page not found", "details": None}})
    await db.delete(page)
    await db.commit()
    return {"status": "deleted"}


@router.get("/bookings", response_model=list[BookingResponse], dependencies=[Depends(require_api_key)])
async def list_bookings(page_id: NullableUUID = None, brand_id: NullableUUID = None, db: AsyncSession = Depends(get_db)):
    ws = await get_singleton(db)
    q = (
        select(CalendarBooking)
        .join(CalendarPage, CalendarBooking.page_id == CalendarPage.id)
        .where(CalendarPage.workspace_id == ws.id)
    )
    if page_id:
        q = q.where(CalendarBooking.page_id == page_id)
    if brand_id:
        q = q.where(CalendarPage.brand_id == brand_id)
    rows = (await db.execute(q.order_by(CalendarBooking.start_at.asc()))).scalars().all()
    return [
        BookingResponse(
            id=str(r.id),
            attendee_name=r.attendee_name,
            attendee_email=r.attendee_email,
            start_at=r.start_at,
            end_at=r.end_at,
            status=r.status,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.delete("/bookings/{booking_id}", dependencies=[Depends(require_api_key)], responses={404: {"description": "Booking not found"}})
async def cancel_booking(booking_id: uuid.UUID, db: AsyncSession = Depends(get_db), settings=Depends(get_settings)):
    ws = await get_singleton(db)
    booking = (await db.execute(
        select(CalendarBooking)
        .join(CalendarPage, CalendarBooking.page_id == CalendarPage.id)
        .where(CalendarBooking.id == booking_id, CalendarPage.workspace_id == ws.id)
    )).scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Booking not found", "details": None}})

    if booking.google_event_id:
        page = (await db.execute(select(CalendarPage).where(CalendarPage.id == booking.page_id))).scalar_one_or_none()
        if page and page.brand_id and page.connection_id:
            token, _ = await get_page_token(db, str(page.brand_id), "google_calendar", settings)
            if token:
                try:
                    async with httpx.AsyncClient(timeout=10.0) as c:
                        await c.delete(
                            f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{booking.google_event_id}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
                except Exception:
                    pass

    booking.status = "cancelled"
    await db.commit()
    return {"status": "cancelled"}


# ── Public: availability & booking ────────────────────────────────────────────

@router.get("/availability/{slug}", response_model=AvailabilityResponse, responses={404: {"description": "Booking page not found"}})
async def get_availability(slug: str, db: AsyncSession = Depends(get_db), settings=Depends(get_settings)):
    page = await _get_public_page(db, slug)

    tz = _tz(page.timezone)
    now = datetime.now(tz)
    start_date = (now + timedelta(days=1)).date()
    end_date = start_date + timedelta(days=page.max_days_ahead)
    range_start = datetime(start_date.year, start_date.month, start_date.day, tzinfo=tz)
    range_end = datetime(end_date.year, end_date.month, end_date.day, tzinfo=tz) + timedelta(days=1)

    existing = (await db.execute(
        select(CalendarBooking).where(
            CalendarBooking.page_id == page.id,
            CalendarBooking.status == "confirmed",
            CalendarBooking.start_at >= range_start,
            CalendarBooking.start_at < range_end,
        )
    )).scalars().all()

    busy: list[tuple[datetime, datetime]] = []
    if page.connection_id and page.brand_id:
        token, _ = await get_page_token(db, str(page.brand_id), "google_calendar", settings)
        if token:
            busy = await _gcal_busy(token, page.timezone, range_start.astimezone(timezone.utc), range_end.astimezone(timezone.utc))

    days = []
    cur = start_date
    while cur < end_date:
        slots = _slots_for_day(page, cur, list(existing), busy)
        if slots:
            days.append(DaySlots(date=cur.isoformat(), slots=slots))
        cur += timedelta(days=1)

    return AvailabilityResponse(
        slug=slug,
        title=page.title,
        description=page.description,
        timezone=page.timezone,
        duration_minutes=page.duration_minutes,
        days=days,
    )


@router.post("/book/{slug}", response_model=BookingResponse)
async def create_booking(slug: str, body: BookingRequest, db: AsyncSession = Depends(get_db), settings=Depends(get_settings)):
    page = await _get_public_page(db, slug)

    tz = _tz(page.timezone)
    try:
        start_at = datetime.fromisoformat(body.start_at)
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=tz)
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_TIME", "message": "Invalid start_at format", "details": None}})

    end_at = start_at + timedelta(minutes=page.duration_minutes)
    buf = timedelta(minutes=page.buffer_minutes)

    local_start = start_at.astimezone(tz)
    now = datetime.now(tz)
    first_bookable_date = (now + timedelta(days=1)).date()
    last_bookable_date = first_bookable_date + timedelta(days=page.max_days_ahead)
    if (
        local_start.second
        or local_start.microsecond
        or local_start.date() < first_bookable_date
        or local_start.date() >= last_bookable_date
    ):
        raise HTTPException(status_code=409, detail={"error": {"code": "SLOT_UNAVAILABLE", "message": "This time slot is not offered", "details": None}})

    day_start = datetime(local_start.year, local_start.month, local_start.day, tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    day_existing = (await db.execute(
        select(CalendarBooking).where(
            CalendarBooking.page_id == page.id,
            CalendarBooking.status == "confirmed",
            CalendarBooking.start_at >= day_start,
            CalendarBooking.start_at < day_end,
        )
    )).scalars().all()
    busy: list[tuple[datetime, datetime]] = []
    if page.connection_id and page.brand_id:
        token, _ = await get_page_token(db, str(page.brand_id), "google_calendar", settings)
        if token:
            busy = await _gcal_busy(token, page.timezone, day_start.astimezone(timezone.utc), day_end.astimezone(timezone.utc))
    if local_start.strftime("%H:%M") not in _slots_for_day(page, local_start.date(), list(day_existing), busy):
        raise HTTPException(status_code=409, detail={"error": {"code": "SLOT_UNAVAILABLE", "message": "This time slot is not offered", "details": None}})

    conflict = (await db.execute(
        select(CalendarBooking).where(
            CalendarBooking.page_id == page.id,
            CalendarBooking.status == "confirmed",
            CalendarBooking.start_at < end_at + buf,
            CalendarBooking.end_at > start_at - buf,
        )
    )).scalar_one_or_none()
    if conflict:
        raise HTTPException(status_code=409, detail={"error": {"code": "SLOT_TAKEN", "message": "This time slot is no longer available", "details": None}})

    booking = CalendarBooking(
        id=uuid.uuid4(),
        page_id=page.id,
        attendee_name=body.attendee_name,
        attendee_email=body.attendee_email,
        start_at=start_at,
        end_at=end_at,
        message=body.message,
        status="confirmed",
    )
    db.add(booking)
    await db.flush()

    if page.connection_id and page.brand_id:
        token, _ = await get_page_token(db, str(page.brand_id), "google_calendar", settings)
        if token:
            event_id = await _gcal_create(token, page, booking)
            if event_id:
                booking.google_event_id = event_id
            await _send_confirm(token, page, booking)

    await db.commit()
    await db.refresh(booking)
    return BookingResponse(
        id=str(booking.id),
        attendee_name=booking.attendee_name,
        attendee_email=booking.attendee_email,
        start_at=booking.start_at,
        end_at=booking.end_at,
        status=booking.status,
        created_at=booking.created_at,
    )


# ── Public: embeddable HTML widget ────────────────────────────────────────────

@router.get("/book/{slug}", response_class=HTMLResponse)
async def booking_widget(slug: str, settings=Depends(get_settings)):
    api_base = settings.frontend_url.rstrip("/") + "/api"
    # frame-ancestors * allows any site to iframe our booking page (WordPress, Webflow, etc.)
    return HTMLResponse(
        _widget_html(slug, api_base),
        headers={"Content-Security-Policy": "frame-ancestors *"},
    )


@router.get("/widget.js", response_class=JavaScriptResponse)
async def booking_widget_js(settings=Depends(get_settings)):
    api_base = settings.frontend_url.rstrip("/") + "/api"
    js = _WIDGET_JS_TEMPLATE.replace("__API_BASE__", api_base)
    return JavaScriptResponse(content=js, headers={"Cache-Control": "public, max-age=3600"})


def _widget_html(slug: str, api_base: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Book a Meeting</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --brand:#0B3D2E;--accent:#826D40;--error:#7A2E2E;
  --linen:#F2E8D0;--copper:#B85C30;--copper-dark:#964926;--gold-light:#C8A870;
  --white:#FFFFFF;--ivory:#F5F1E8;--obsidian:#080B0D;
  --ink:#0B3D2E;--ink-body:#2C4A3E;--ink-muted:#4A6B5C;--ink-subtle:#6B8F7E;
  --border:rgba(11,61,46,.15);--border-warm:rgba(130,109,64,.22);
  --radius:2px;--font-ui:'Inter',system-ui,sans-serif;--font-display:'Manrope',system-ui,sans-serif;
}}
html,body{{height:100%;background:var(--white);color:var(--ink-body);font-family:var(--font-ui);font-size:15px;line-height:1.5}}
#app{{max-width:640px;margin:0 auto;padding:32px 24px 64px}}
h1{{font-family:var(--font-display);font-size:22px;font-weight:700;letter-spacing:-.02em;margin-bottom:4px;color:var(--ink)}}
.desc{{color:var(--ink-muted);font-size:14px;margin-bottom:32px}}
.label{{font-family:var(--font-display);font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin-bottom:10px}}
/* Date strip */
.dates{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:28px}}
.date-btn{{border:.5px solid var(--border);background:var(--white);border-radius:var(--radius);padding:8px 14px;cursor:pointer;font-size:13px;font-weight:500;transition:all .15s;white-space:nowrap;color:var(--ink-body)}}
.date-btn:hover{{border-color:var(--brand);color:var(--brand);background:rgba(11,61,46,.05)}}
.date-btn.active{{background:transparent;border-color:var(--brand);color:var(--brand);box-shadow:inset 0 -1.5px 0 var(--brand);font-weight:600}}
.date-btn.no-slots{{opacity:.4;cursor:default;pointer-events:none}}
/* Slots */
.slots{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:32px}}
.slot-btn{{border:.5px solid var(--border);background:var(--white);border-radius:var(--radius);padding:9px 18px;cursor:pointer;font-size:14px;font-weight:500;transition:all .15s;color:var(--ink-body)}}
.slot-btn:hover{{border-color:var(--brand);color:var(--brand);background:rgba(11,61,46,.05)}}
.slot-btn.active{{background:transparent;border-color:var(--brand);color:var(--brand);box-shadow:inset 0 -1.5px 0 var(--brand);font-weight:600}}
/* Form */
form{{display:flex;flex-direction:column;gap:14px}}
input,textarea{{width:100%;padding:12px 14px;border:.5px solid rgba(11,61,46,.3);border-radius:var(--radius);font-size:14px;font-family:inherit;background:var(--white);transition:border-color .15s;outline:none;color:var(--ink)}}
input:focus,textarea:focus{{border-color:var(--accent)}}
input::placeholder,textarea::placeholder{{color:var(--ink-subtle)}}
textarea{{resize:vertical;min-height:80px}}
.btn-submit{{background:var(--copper);color:var(--ivory);border:.5px solid var(--copper);border-radius:var(--radius);padding:13px 28px;font-size:15px;font-weight:600;cursor:pointer;transition:background .15s;align-self:flex-start}}
.btn-submit:hover{{background:var(--copper-dark);border-color:var(--copper-dark)}}
.btn-submit:disabled{{background:rgba(184,92,48,.28);border-color:transparent;color:rgba(245,241,232,.50);cursor:default}}
/* Confirmed */
#confirmed{{text-align:center;padding:48px 0}}
.check-icon{{width:56px;height:56px;background:var(--white);border:.5px solid var(--brand);border-radius:0;display:flex;align-items:center;justify-content:center;margin:0 auto 20px}}
.check-icon svg{{stroke:var(--brand);stroke-width:2.5}}
#confirmed h2{{font-family:var(--font-display);font-size:20px;font-weight:700;margin-bottom:8px;color:var(--ink)}}
#confirmed p{{color:var(--ink-muted);font-size:14px}}
.confirm-details{{background:var(--white);border:.5px solid var(--border);border-left:2px solid var(--brand);border-radius:0;padding:16px 20px;margin:20px auto 0;max-width:340px;font-size:14px;text-align:left}}
.confirm-details strong{{display:block;margin-bottom:4px;font-size:11px;color:var(--accent);font-weight:700;text-transform:uppercase;letter-spacing:.14em;font-family:var(--font-display)}}
/* Error / loading */
#loading{{color:var(--ink-muted);font-size:14px;padding:24px 0}}
.err{{color:var(--error);font-size:13px;margin-top:-6px}}
.sep{{height:.5px;background:var(--border);margin:4px 0 24px}}
</style>
</head>
<body>
<div id="app">
  <div id="loading">Loading availability…</div>
  <div id="calendar" style="display:none">
    <h1 id="pg-title"></h1>
    <p class="desc" id="pg-desc"></p>
    <div class="label" id="label-date">Select a date</div>
    <div class="dates" id="date-list"></div>
    <div id="slot-section" style="display:none">
      <div class="label">Select a time <span id="tz-note" style="text-transform:none;font-weight:400;letter-spacing:0;font-size:11px;color:var(--text-secondary)"></span></div>
      <div class="slots" id="slot-list"></div>
    </div>
    <div id="form-section" style="display:none">
      <div class="sep"></div>
      <div class="label">Your details</div>
      <form id="booking-form">
        <input id="f-name" type="text" placeholder="Your name" required>
        <input id="f-email" type="email" placeholder="Email address" required>
        <textarea id="f-msg" placeholder="Anything you'd like to share? (optional)"></textarea>
        <p class="err" id="form-err" style="display:none"></p>
        <button type="submit" class="btn-submit" id="submit-btn">Confirm booking</button>
      </form>
    </div>
  </div>
  <div id="confirmed" style="display:none">
    <div class="check-icon"><svg width="28" height="28" viewBox="0 0 24 24" fill="none"><polyline points="20 6 9 17 4 12"/></svg></div>
    <h2>You're booked!</h2>
    <p>A confirmation has been sent to your email.</p>
    <div class="confirm-details">
      <strong>Meeting</strong><span id="c-title"></span>
      <strong style="margin-top:12px">When</strong><span id="c-when"></span>
    </div>
  </div>
</div>
<script>
(function(){{
  const API="{api_base}",SLUG="{slug}";
  let avail=null,selDate=null,selSlot=null,tz="UTC",dur=30;
  const visitorTz=Intl.DateTimeFormat().resolvedOptions().timeZone;

  // Convert a slot (date string + hhmm in hostTz) to a proper UTC Date.
  // Uses Intl to find the exact UTC offset at that moment, handles DST correctly.
  function slotToUTC(isoDate,hhmm,hostTz){{
    const [h,m]=hhmm.split(":").map(Number);
    const [y,mo,d]=isoDate.split("-").map(Number);
    let est=new Date(Date.UTC(y,mo-1,d,h,m));
    const parts=new Intl.DateTimeFormat("en-US",{{timeZone:hostTz,hour:"2-digit",minute:"2-digit",hour12:false}}).formatToParts(est);
    const gotH=parseInt(parts.find(p=>p.type==="hour").value)%24;
    const gotM=parseInt(parts.find(p=>p.type==="minute").value);
    const diffMin=(h*60+m)-(gotH*60+gotM);
    return new Date(est.getTime()-diffMin*60000);
  }}

  async function load(){{
    try{{
      const r=await fetch(API+"/calendar/availability/"+SLUG);
      if(!r.ok)throw new Error("Not found");
      avail=await r.json();
      tz=avail.timezone;dur=avail.duration_minutes;
      document.getElementById("pg-title").textContent=avail.title;
      const d=document.getElementById("pg-desc");
      if(avail.description){{d.textContent=avail.description}}else{{d.style.display="none"}}
      renderDates();
      document.getElementById("loading").style.display="none";
      document.getElementById("calendar").style.display="block";
    }}catch(e){{
      document.getElementById("loading").textContent="This booking page is not available.";
    }}
  }}

  function fmtDate(iso){{
    // Use noon to avoid date shifting for visitors in UTC± edge zones
    return new Date(iso+"T12:00:00").toLocaleDateString("en-US",{{weekday:"short",month:"short",day:"numeric"}});
  }}

  function fmtSlot(isoDate,hhmm,hostTz){{
    // Convert from host timezone to visitor's local timezone for display
    return slotToUTC(isoDate,hhmm,hostTz).toLocaleTimeString("en-US",{{hour:"numeric",minute:"2-digit",hour12:true}});
  }}

  function renderDates(){{
    const el=document.getElementById("date-list");
    el.innerHTML="";
    (avail.days||[]).forEach(day=>{{
      const btn=document.createElement("button");
      btn.className="date-btn"+(day.slots.length===0?" no-slots":"");
      btn.textContent=fmtDate(day.date);
      btn.dataset.date=day.date;
      btn.addEventListener("click",()=>selectDate(day));
      el.appendChild(btn);
    }});
  }}

  function selectDate(day){{
    selDate=day;selSlot=null;
    document.querySelectorAll(".date-btn").forEach(b=>b.classList.toggle("active",b.dataset.date===day.date));
    document.getElementById("slot-section").style.display="block";
    document.getElementById("form-section").style.display="none";
    // Show timezone note when slot grid appears
    const note=document.getElementById("tz-note");
    if(note)note.textContent=visitorTz===tz?"("+tz+")":"· your time ("+visitorTz+")";
    const el=document.getElementById("slot-list");
    el.innerHTML="";
    day.slots.forEach(s=>{{
      const btn=document.createElement("button");
      btn.className="slot-btn";
      btn.textContent=fmtSlot(day.date,s,tz);
      btn.dataset.slot=s;
      btn.addEventListener("click",()=>selectSlot(day.date,s,btn));
      el.appendChild(btn);
    }});
  }}

  function selectSlot(isoDate,hhmm,btn){{
    selSlot={{date:isoDate,time:hhmm}};
    document.querySelectorAll(".slot-btn").forEach(b=>b.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("form-section").style.display="block";
  }}

  document.getElementById("booking-form").addEventListener("submit",async function(e){{
    e.preventDefault();
    if(!selSlot)return;
    const name=document.getElementById("f-name").value.trim();
    const email=document.getElementById("f-email").value.trim();
    const msg=document.getElementById("f-msg").value.trim();
    const errEl=document.getElementById("form-err");
    errEl.style.display="none";
    const btn=document.getElementById("submit-btn");
    btn.disabled=true;btn.textContent="Booking…";

    // Correctly convert slot from host timezone to UTC before sending
    const startDt=slotToUTC(selSlot.date,selSlot.time,tz);

    try{{
      const r=await fetch(API+"/calendar/book/"+SLUG,{{
        method:"POST",
        headers:{{"Content-Type":"application/json"}},
        body:JSON.stringify({{attendee_name:name,attendee_email:email,start_at:startDt.toISOString(),message:msg||null}}),
      }});
      const data=await r.json();
      if(!r.ok){{
        const msg2=(data.error&&data.error.message)||"Something went wrong. Please try again.";
        errEl.textContent=msg2;errEl.style.display="block";
        btn.disabled=false;btn.textContent="Confirm booking";
        return;
      }}
      document.getElementById("c-title").textContent=avail.title;
      const start=new Date(data.start_at);
      const localStr=start.toLocaleString("en-US",{{weekday:"long",year:"numeric",month:"long",day:"numeric",hour:"numeric",minute:"2-digit",hour12:true}});
      const hostStr=start.toLocaleTimeString("en-US",{{hour:"numeric",minute:"2-digit",hour12:true,timeZone:tz}});
      const whenText=visitorTz===tz
        ?localStr+" ("+tz+")"
        :localStr+" your time · "+hostStr+" "+tz;
      document.getElementById("c-when").textContent=whenText;
      document.getElementById("calendar").style.display="none";
      document.getElementById("confirmed").style.display="block";
    }}catch(ex){{
      errEl.textContent="Network error. Please try again.";errEl.style.display="block";
      btn.disabled=false;btn.textContent="Confirm booking";
    }}
  }});

  load();
}})();
</script>
</body>
</html>"""


# Embed on any site: <div data-klaroha-booking="your-slug"></div>
#                    <script src="https://yourdomain.com/api/calendar/widget.js" async></script>
_WIDGET_JS_TEMPLATE = r"""(function () {
  'use strict';
  var API = '__API_BASE__';

  function injectStyles() {
    if (document.getElementById('klr-widget-styles')) return;
    var s = document.createElement('style');
    s.id = 'klr-widget-styles';
    s.textContent = '.klr-iframe{width:100%;border:0;border-radius:8px;display:block;min-height:640px}';
    document.head.appendChild(s);
  }

  function init() {
    injectStyles();
    document.querySelectorAll('[data-klaroha-booking]').forEach(function (el) {
      var slug = el.getAttribute('data-klaroha-booking');
      if (!slug) return;
      var iframe = document.createElement('iframe');
      iframe.className = 'klr-iframe';
      iframe.src = API + '/calendar/book/' + slug;
      iframe.title = 'Book a meeting';
      el.appendChild(iframe);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
"""
