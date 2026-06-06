import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import recurring_ical_events
from api.auth import PersonAuth, get_person_auth
from api.db import get_session
from api.models import Event, Group, Membership, Person, Reminder
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from icalendar import Alarm, Calendar, vRecur
from icalendar import Event as ICalEvent
from pydantic import BaseModel
from sqlmodel import Session, select

router = APIRouter()

_ICAL_WINDOW_DAYS = 365


class RotateResponse(BaseModel):
    new_feed_url: str


def _build_ical_calendar(events: list[Event], reminders: list[Reminder]) -> bytes:
    cal = Calendar()
    cal.add("PRODID", "-//Household Manager//EN")
    cal.add("VERSION", "2.0")
    cal.add("CALSCALE", "GREGORIAN")

    window_start = datetime.now(tz=UTC)
    window_end = window_start + timedelta(days=_ICAL_WINDOW_DAYS)

    for event in events:
        if event.rrule:
            temp_cal = Calendar()
            vevent = ICalEvent()
            vevent.add("SUMMARY", event.title)
            starts = event.starts_at
            if starts.tzinfo is None:
                starts = starts.replace(tzinfo=UTC)
            vevent.add("DTSTART", starts)
            vevent.add("UID", str(event.id))
            vevent.add("RRULE", vRecur.from_ical(event.rrule))
            temp_cal.add_component(vevent)

            occurrences = recurring_ical_events.of(temp_cal).between(window_start, window_end)
            for occ in occurrences:
                cal.add_component(occ)
        else:
            vevent = ICalEvent()
            vevent.add("SUMMARY", event.title)
            starts = event.starts_at
            if starts.tzinfo is None:
                starts = starts.replace(tzinfo=UTC)
            vevent.add("DTSTART", starts)
            vevent.add("UID", str(event.id))
            cal.add_component(vevent)

    for reminder in reminders:
        fire_at = reminder.fire_at
        if fire_at.tzinfo is None:
            fire_at = fire_at.replace(tzinfo=UTC)

        vevent = ICalEvent()
        vevent.add("SUMMARY", reminder.title)
        vevent.add("DTSTART", fire_at)
        vevent.add("DTEND", fire_at)
        vevent.add("UID", f"reminder-{reminder.id}")

        alarm = Alarm()
        alarm.add("ACTION", "DISPLAY")
        alarm.add("TRIGGER", timedelta(minutes=-5))
        alarm.add("DESCRIPTION", reminder.title)
        vevent.add_component(alarm)

        cal.add_component(vevent)

    return cal.to_ical()


def _get_reachable_group_ids(session: Session, person_id: uuid.UUID) -> set[uuid.UUID]:
    # Collect direct memberships, then traverse child groups breadth-first.
    # This rollup logic mirrors person_reachable_groups() used in Postgres RLS.
    direct = session.exec(
        select(Membership.group_id).where(Membership.person_id == person_id)
    ).all()
    reachable: set[uuid.UUID] = set(direct)
    frontier: list[uuid.UUID] = list(reachable)

    while frontier:
        children = session.exec(select(Group.id).where(Group.parent_group_id.in_(frontier))).all()
        new_children = set(children) - reachable
        reachable.update(new_children)
        frontier = list(new_children)

    return reachable


def _fetch_reminders_for_person(session: Session, person_id: uuid.UUID) -> list[Reminder]:
    # Include delivered reminders and undelivered future reminders so the
    # calendar app shows both past alerts and upcoming ones.
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    return session.exec(
        select(Reminder).where(
            Reminder.person_id == person_id,
            (Reminder.delivered == True) | (Reminder.fire_at > now),  # noqa: E712
        )
    ).all()


def _fetch_events_for_person(session: Session, person_id: uuid.UUID) -> list[Event]:
    group_ids = _get_reachable_group_ids(session, person_id)
    if not group_ids:
        return []

    return session.exec(select(Event).where(Event.group_id.in_(list(group_ids)))).all()


@router.get("/ical/{secret}")
def get_ical_feed(
    secret: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    person = session.exec(select(Person).where(Person.ical_secret == secret)).first()
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed not found",
        )

    events = _fetch_events_for_person(session, person.id)
    reminders = _fetch_reminders_for_person(session, person.id)
    cal_bytes = _build_ical_calendar(events, reminders)

    return Response(
        content=cal_bytes,
        media_type="text/calendar; charset=utf-8",
    )


@router.post("/ical/rotate", response_model=RotateResponse)
def rotate_ical_secret(
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> RotateResponse:
    person = session.exec(select(Person).where(Person.id == auth.person_id)).first()
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found — call POST /person/sync first",
        )

    new_secret = uuid.uuid4()
    person.ical_secret = new_secret
    session.add(person)
    session.commit()

    app_url = os.environ.get("VERCEL_URL", "http://localhost:8000")
    if not app_url.startswith("http"):
        app_url = f"https://{app_url}"

    return RotateResponse(new_feed_url=f"{app_url}/api/v1/ical/{new_secret}")
