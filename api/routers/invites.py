import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from api.auth import get_person_auth, PersonAuth
from api.db import get_session
from api.models import Group, Invite, Membership

router = APIRouter()


class InviteCreate(BaseModel):
    expires_at: datetime | None
    max_uses: int | None

    model_config = {"extra": "forbid"}


class InviteResponse(BaseModel):
    id: uuid.UUID
    token: str
    invite_url: str
    expires_at: datetime | None
    max_uses: int | None
    uses: int


class AcceptResponse(BaseModel):
    group_id: uuid.UUID
    group_name: str
    role: str


def _invite_url(token: str) -> str:
    base = os.environ.get("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
    return f"{base}/join/{token}"


def _is_valid_invite(invite: Invite) -> bool:
    now = datetime.now(timezone.utc)
    if invite.expires_at is not None:
        exp = invite.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= now:
            return False
    if invite.max_uses is not None and invite.uses >= invite.max_uses:
        return False
    return True


@router.post(
    "/groups/{group_id}/invites",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invite(
    group_id: uuid.UUID,
    body: InviteCreate,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> InviteResponse:
    """Generate invite token for a group. Caller must be owner."""
    membership = session.exec(
        select(Membership).where(
            Membership.person_id == auth.person_id,
            Membership.group_id == group_id,
        )
    ).first()

    if not membership or membership.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can generate invite links",
        )

    token = secrets.token_hex(32)  # 64-char hex

    invite = Invite(
        group_id=group_id,
        created_by=auth.person_id,
        token=token,
        expires_at=body.expires_at,
        max_uses=body.max_uses,
        uses=0,
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)

    return InviteResponse(
        id=invite.id,
        token=invite.token,
        invite_url=_invite_url(invite.token),
        expires_at=invite.expires_at,
        max_uses=invite.max_uses,
        uses=invite.uses,
    )


@router.post("/invites/{token}/accept", response_model=AcceptResponse)
def accept_invite(
    token: str,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> AcceptResponse:
    """Accept an invite token. Creates a membership for the caller."""
    invite = session.exec(select(Invite).where(Invite.token == token)).first()

    if not invite or not _is_valid_invite(invite):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invite token is expired or exhausted",
        )

    group = session.get(Group, invite.group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    existing = session.exec(
        select(Membership).where(
            Membership.person_id == auth.person_id,
            Membership.group_id == invite.group_id,
        )
    ).first()

    if existing:
        return AcceptResponse(
            group_id=group.id,
            group_name=group.name,
            role=existing.role,
        )

    membership = Membership(
        person_id=auth.person_id,
        group_id=invite.group_id,
        role="member",
    )
    session.add(membership)

    invite.uses += 1
    session.add(invite)

    session.commit()

    return AcceptResponse(
        group_id=group.id,
        group_name=group.name,
        role="member",
    )
