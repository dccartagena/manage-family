import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from api.auth import PersonAuth, get_person_auth
from api.db import get_session
from api.models import Event, Group, Membership, ShoppingItem, Task
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

router = APIRouter()


class DashboardTask(BaseModel):
    id: uuid.UUID
    title: str
    group_name: str
    due_at: datetime | None


class DashboardEvent(BaseModel):
    id: uuid.UUID
    title: str
    group_name: str
    starts_at: datetime


class DashboardShoppingCount(BaseModel):
    group_id: uuid.UUID
    group_name: str
    unchecked_count: int


class DashboardResponse(BaseModel):
    overdue_tasks: list[DashboardTask]
    today_tasks: list[DashboardTask]
    today_events: list[DashboardEvent]
    shopping_counts: list[DashboardShoppingCount]
    upcoming_events: list[DashboardEvent]


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> DashboardResponse:
    now_naive = datetime.now(UTC).replace(tzinfo=None)
    today_start = now_naive.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    seven_days_end = today_end + timedelta(days=7)

    memberships = session.exec(
        select(Membership).where(Membership.person_id == auth.person_id)
    ).all()
    group_ids = [m.group_id for m in memberships]

    if not group_ids:
        return DashboardResponse(
            overdue_tasks=[],
            today_tasks=[],
            today_events=[],
            shopping_counts=[],
            upcoming_events=[],
        )

    groups = session.exec(select(Group).where(Group.id.in_(group_ids))).all()
    group_name_map: dict[uuid.UUID, str] = {g.id: g.name for g in groups}

    overdue_rows = session.exec(
        select(Task).where(
            Task.group_id.in_(group_ids),
            Task.done == False,  # noqa: E712
            Task.due_at != None,  # noqa: E711
            Task.due_at < today_start,
        )
    ).all()

    today_task_rows = session.exec(
        select(Task).where(
            Task.group_id.in_(group_ids),
            Task.done == False,  # noqa: E712
            Task.due_at != None,  # noqa: E711
            Task.due_at >= today_start,
            Task.due_at < today_end,
        )
    ).all()

    today_event_rows = session.exec(
        select(Event).where(
            Event.group_id.in_(group_ids),
            Event.starts_at >= today_start,
            Event.starts_at < today_end,
        )
    ).all()

    shopping_counts: list[DashboardShoppingCount] = []
    for group_id in group_ids:
        unchecked_count = session.exec(
            select(func.count())
            .select_from(ShoppingItem)
            .where(
                ShoppingItem.group_id == group_id,
                ShoppingItem.checked == False,  # noqa: E712
            )
        ).one()
        shopping_counts.append(
            DashboardShoppingCount(
                group_id=group_id,
                group_name=group_name_map[group_id],
                unchecked_count=unchecked_count,
            )
        )

    upcoming_event_rows = session.exec(
        select(Event).where(
            Event.group_id.in_(group_ids),
            Event.starts_at >= today_end,
            Event.starts_at < seven_days_end,
        )
    ).all()

    return DashboardResponse(
        overdue_tasks=[
            DashboardTask(
                id=t.id,
                title=t.title,
                group_name=group_name_map[t.group_id],
                due_at=t.due_at,
            )
            for t in overdue_rows
        ],
        today_tasks=[
            DashboardTask(
                id=t.id,
                title=t.title,
                group_name=group_name_map[t.group_id],
                due_at=t.due_at,
            )
            for t in today_task_rows
        ],
        today_events=[
            DashboardEvent(
                id=e.id,
                title=e.title,
                group_name=group_name_map[e.group_id],
                starts_at=e.starts_at,
            )
            for e in today_event_rows
        ],
        shopping_counts=shopping_counts,
        upcoming_events=[
            DashboardEvent(
                id=e.id,
                title=e.title,
                group_name=group_name_map[e.group_id],
                starts_at=e.starts_at,
            )
            for e in upcoming_event_rows
        ],
    )
