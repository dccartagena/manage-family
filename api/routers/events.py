import uuid
from datetime import datetime
from typing import Annotated

from api.auth import PersonAuth, get_person_auth
from api.db import get_session
from api.models import Event, Membership
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

router = APIRouter()


class EventCreate(BaseModel):
    title: str
    starts_at: datetime
    rrule: str | None = None

    model_config = {"extra": "forbid"}


class EventResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    title: str
    starts_at: datetime
    rrule: str | None


def _get_membership(
    session: Session,
    person_id: uuid.UUID,
    group_id: uuid.UUID,
) -> Membership | None:
    return session.exec(
        select(Membership).where(
            Membership.person_id == person_id,
            Membership.group_id == group_id,
        )
    ).first()


def _event_to_response(event: Event) -> EventResponse:
    return EventResponse(
        id=event.id,
        group_id=event.group_id,
        title=event.title,
        starts_at=event.starts_at,
        rrule=event.rrule,
    )


@router.get("/groups/{group_id}/events", response_model=list[EventResponse])
def list_events(
    group_id: uuid.UUID,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> list[EventResponse]:
    # Event RLS (person_reachable_groups) handles rollup in production Postgres.
    # App-layer membership check ensures 403 for non-members in all environments.
    membership = _get_membership(session, auth.person_id, group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    events = session.exec(select(Event).where(Event.group_id == group_id)).all()
    return [_event_to_response(e) for e in events]


@router.post(
    "/groups/{group_id}/events",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    group_id: uuid.UUID,
    body: EventCreate,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> EventResponse:
    membership = _get_membership(session, auth.person_id, group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    event = Event(
        group_id=group_id,
        title=body.title,
        starts_at=body.starts_at,
        rrule=body.rrule,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return _event_to_response(event)


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: uuid.UUID,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    event = session.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    membership = _get_membership(session, auth.person_id, event.group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    session.delete(event)
    session.commit()
