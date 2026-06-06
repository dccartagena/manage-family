import uuid
from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from api.auth import PersonAuth, get_person_auth
from api.db import get_session
from api.models import Reminder
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

router = APIRouter()


class ReminderCreate(BaseModel):
    title: str
    fire_at_local: datetime
    timezone: str

    model_config = {"extra": "forbid"}


class ReminderResponse(BaseModel):
    id: uuid.UUID
    title: str
    fire_at: datetime
    delivered: bool


def _reminder_to_response(reminder: Reminder) -> ReminderResponse:
    return ReminderResponse(
        id=reminder.id,
        title=reminder.title,
        fire_at=reminder.fire_at,
        delivered=reminder.delivered,
    )


@router.get("/reminders", response_model=list[ReminderResponse])
def list_reminders(
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ReminderResponse]:
    reminders = session.exec(
        select(Reminder).where(Reminder.person_id == auth.person_id)
    ).all()
    return [_reminder_to_response(r) for r in reminders]


@router.post("/reminders", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
def create_reminder(
    body: ReminderCreate,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> ReminderResponse:
    try:
        tz = ZoneInfo(body.timezone)
    except ZoneInfoNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown timezone: {body.timezone}",
        ) from err

    local_dt = body.fire_at_local.replace(tzinfo=tz)
    fire_at_utc = local_dt.astimezone(UTC).replace(tzinfo=None)

    reminder = Reminder(
        person_id=auth.person_id,
        title=body.title,
        fire_at=fire_at_utc,
    )
    session.add(reminder)
    session.commit()
    session.refresh(reminder)
    return _reminder_to_response(reminder)


@router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: uuid.UUID,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    reminder = session.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found",
        )
    if reminder.person_id != auth.person_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your reminder",
        )
    session.delete(reminder)
    session.commit()
