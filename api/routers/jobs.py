import os
from datetime import UTC, datetime
from typing import Annotated

from api.db import get_session
from api.models import Reminder
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

router = APIRouter()


class TickResponse(BaseModel):
    reminders_delivered: int
    tick_at: str


@router.get("/jobs/tick", response_model=TickResponse)
def tick(
    session: Annotated[Session, Depends(get_session)],
    x_scheduler_secret: Annotated[str | None, Header()] = None,
) -> TickResponse:
    expected = os.environ.get("SCHEDULER_SECRET", "")
    if not expected or x_scheduler_secret != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing scheduler secret",
        )

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    due_reminders = session.exec(
        select(Reminder).where(
            Reminder.fire_at <= now,
            Reminder.delivered == False,  # noqa: E712
        )
    ).all()

    for reminder in due_reminders:
        reminder.delivered = True
        session.add(reminder)

    session.commit()

    return TickResponse(
        reminders_delivered=len(due_reminders),
        tick_at=datetime.now(tz=UTC).isoformat(),
    )
