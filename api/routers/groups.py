import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from api.auth import get_person_auth, PersonAuth
from api.db import get_session
from api.models import Group, Membership, Task

router = APIRouter()


class GroupCreate(BaseModel):
    name: str
    parent_group_id: uuid.UUID | None = None

    model_config = {"extra": "forbid"}


class GroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    parent_group_id: uuid.UUID | None
    depth: int
    role: str


class GroupListItem(BaseModel):
    id: uuid.UUID
    name: str
    depth: int
    role: str


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


@router.post("/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    body: GroupCreate,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> GroupResponse:
    """Create a new household group. Caller becomes owner."""
    depth = 0
    if body.parent_group_id is not None:
        parent = session.get(Group, body.parent_group_id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent group not found",
            )
        if parent.depth >= 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent group is at maximum nesting depth (4); cannot create sub-group",
            )
        depth = parent.depth + 1

    group = Group(
        name=body.name,
        parent_group_id=body.parent_group_id,
        depth=depth,
    )
    session.add(group)
    session.flush()

    membership = Membership(
        person_id=auth.person_id,
        group_id=group.id,
        role="owner",
    )
    session.add(membership)
    session.commit()
    session.refresh(group)

    return GroupResponse(
        id=group.id,
        name=group.name,
        parent_group_id=group.parent_group_id,
        depth=group.depth,
        role="owner",
    )


@router.get("/groups", response_model=list[GroupListItem])
def list_groups(
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> list[GroupListItem]:
    """List all groups the caller is a member of."""
    memberships = session.exec(
        select(Membership).where(Membership.person_id == auth.person_id)
    ).all()

    result: list[GroupListItem] = []
    for m in memberships:
        group = session.get(Group, m.group_id)
        if group:
            result.append(
                GroupListItem(
                    id=group.id,
                    name=group.name,
                    depth=group.depth,
                    role=m.role,
                )
            )
    return result


@router.delete(
    "/groups/{group_id}/membership",
    status_code=status.HTTP_204_NO_CONTENT,
)
def leave_group(
    group_id: uuid.UUID,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Leave a group. Triggers auto-promotion or group deletion per owner-departure rules."""
    membership = _get_membership(session, auth.person_id, group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    all_members = session.exec(
        select(Membership).where(Membership.group_id == group_id)
    ).all()

    if len(all_members) == 1:
        # Sole member — delete group and cascade all associated data
        _delete_group_cascade(session, group_id)
        return

    if membership.role == "owner":
        # Other members exist — promote member with smallest joined_at
        other_members = [m for m in all_members if m.person_id != auth.person_id]
        next_owner = min(other_members, key=lambda m: m.joined_at)
        next_owner.role = "owner"
        session.add(next_owner)

    # Clear assignee_id on tasks assigned to departing member in this group (FR-022)
    assigned_tasks = session.exec(
        select(Task).where(
            Task.group_id == group_id,
            Task.assignee_id == auth.person_id,
        )
    ).all()
    for task in assigned_tasks:
        task.assignee_id = None
        session.add(task)

    session.delete(membership)
    session.commit()


def _delete_group_cascade(session: Session, group_id: uuid.UUID) -> None:
    """Delete group and all associated data (tasks, shopping items, events, invites, memberships)."""
    from api.models import Event, Invite, Membership, Reminder, ShoppingItem, Task

    for task in session.exec(select(Task).where(Task.group_id == group_id)).all():
        session.delete(task)

    for item in session.exec(
        select(ShoppingItem).where(ShoppingItem.group_id == group_id)
    ).all():
        session.delete(item)

    for event in session.exec(select(Event).where(Event.group_id == group_id)).all():
        session.delete(event)

    for invite in session.exec(select(Invite).where(Invite.group_id == group_id)).all():
        session.delete(invite)

    for m in session.exec(
        select(Membership).where(Membership.group_id == group_id)
    ).all():
        session.delete(m)

    group = session.get(Group, group_id)
    if group:
        session.delete(group)

    session.commit()
