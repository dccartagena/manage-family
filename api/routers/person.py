import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from api.auth import PersonAuth, get_person_auth
from api.db import get_session
from api.models import Person

router = APIRouter()

_VALID_TEXT_SIZES = frozenset({"normal", "large", "xlarge"})
_VALID_CONTRASTS = frozenset({"normal", "high"})
_VALID_NOTIFICATION_BATCHING = frozenset({"immediate", "morning_summary"})


class PersonResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    ui_prefs: dict[str, Any]
    ical_secret: uuid.UUID


class UiPrefsUpdate(BaseModel):
    text_size: str | None
    contrast: str | None
    reduce_motion: bool | None
    notification_batching: str | None

    model_config = {"extra": "forbid"}


@router.post("/person/sync", response_model=PersonResponse)
def sync_person(
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> PersonResponse:
    """Upsert Person row from JWT claims. Idempotent on repeated calls."""
    existing = session.exec(
        select(Person).where(Person.id == auth.person_id)
    ).first()

    if existing:
        return PersonResponse(
            id=existing.id,
            email=existing.email,
            display_name=existing.display_name,
            ui_prefs=existing.ui_prefs,
            ical_secret=existing.ical_secret,
        )

    display_name = auth.email.split("@")[0] if auth.email else str(auth.person_id)
    person = Person(
        id=auth.person_id,
        email=auth.email,
        display_name=display_name,
    )
    session.add(person)
    session.commit()
    session.refresh(person)

    return PersonResponse(
        id=person.id,
        email=person.email,
        display_name=person.display_name,
        ui_prefs=person.ui_prefs,
        ical_secret=person.ical_secret,
    )


@router.patch("/person/prefs", response_model=dict[str, Any])
def update_prefs(
    body: UiPrefsUpdate,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, Any]:
    """Partial update of caller's ui_prefs JSONB. Returns updated ui_prefs."""
    person = session.exec(
        select(Person).where(Person.id == auth.person_id)
    ).first()

    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found — call POST /person/sync first",
        )

    updated = dict(person.ui_prefs)

    if body.text_size is not None:
        if body.text_size not in _VALID_TEXT_SIZES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"text_size must be one of {sorted(_VALID_TEXT_SIZES)}",
            )
        updated["text_size"] = body.text_size

    if body.contrast is not None:
        if body.contrast not in _VALID_CONTRASTS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"contrast must be one of {sorted(_VALID_CONTRASTS)}",
            )
        updated["contrast"] = body.contrast

    if body.reduce_motion is not None:
        updated["reduce_motion"] = str(body.reduce_motion).lower()

    if body.notification_batching is not None:
        if body.notification_batching not in _VALID_NOTIFICATION_BATCHING:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"notification_batching must be one of {sorted(_VALID_NOTIFICATION_BATCHING)}",
            )
        updated["notification_batching"] = body.notification_batching

    person.ui_prefs = updated
    session.add(person)
    session.commit()
    session.refresh(person)

    return dict(person.ui_prefs)
