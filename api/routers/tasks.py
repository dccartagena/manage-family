import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from api.auth import PersonAuth, get_person_auth
from api.db import get_session
from api.models import Membership, Task

router = APIRouter()


class TaskCreate(BaseModel):
    title: str
    rrule: str | None
    due_at: datetime | None
    assignee_id: uuid.UUID | None

    model_config = {"extra": "forbid"}


class TaskUpdate(BaseModel):
    title: str | None = None
    assignee_id: uuid.UUID | None = None
    due_at: datetime | None = None
    rrule: str | None = None

    model_config = {"extra": "forbid"}


class TaskResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    title: str
    rrule: str | None
    due_at: datetime | None
    done: bool
    assignee_id: uuid.UUID | None


class DoneResponse(BaseModel):
    task: TaskResponse
    next_occurrence: TaskResponse | None


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


def _task_to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        group_id=task.group_id,
        title=task.title,
        rrule=task.rrule,
        due_at=task.due_at,
        done=task.done,
        assignee_id=task.assignee_id,
    )


def _compute_next_occurrence(rrule_str: str, current_due_at: datetime | None) -> datetime | None:
    # rrulestr needs a dtstart to anchor relative rules like FREQ=WEEKLY
    from dateutil.rrule import rrulestr

    dtstart = current_due_at or datetime.utcnow()
    try:
        rule = rrulestr(rrule_str, dtstart=dtstart, ignoretz=False)
        return rule.after(dtstart)
    except Exception:
        return None


@router.get("/groups/{group_id}/tasks", response_model=list[TaskResponse])
def list_tasks(
    group_id: uuid.UUID,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
    done: bool | None = None,
    assignee_id: uuid.UUID | None = None,
) -> list[TaskResponse]:
    """List tasks for a group. Returns done=FALSE by default unless ?done=true specified."""
    membership = _get_membership(session, auth.person_id, group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    query = select(Task).where(Task.group_id == group_id)

    if done is None:
        query = query.where(Task.done == False)  # noqa: E712
    else:
        query = query.where(Task.done == done)  # noqa: E712

    if assignee_id is not None:
        query = query.where(Task.assignee_id == assignee_id)

    tasks = session.exec(query).all()
    return [_task_to_response(t) for t in tasks]


@router.post(
    "/groups/{group_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    group_id: uuid.UUID,
    body: TaskCreate,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> TaskResponse:
    """Create a task in a group. Caller must be a member."""
    membership = _get_membership(session, auth.person_id, group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    task = Task(
        group_id=group_id,
        title=body.title,
        rrule=body.rrule,
        due_at=body.due_at,
        assignee_id=body.assignee_id,
        done=False,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return _task_to_response(task)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> TaskResponse:
    """Partial update of task fields. Caller must be a member of the task's group."""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    membership = _get_membership(session, auth.person_id, task.group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    task.updated_at = datetime.utcnow()
    session.add(task)
    session.commit()
    session.refresh(task)
    return _task_to_response(task)


@router.post("/tasks/{task_id}/done", response_model=DoneResponse)
def mark_task_done(
    task_id: uuid.UUID,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> DoneResponse:
    """Mark task done. If recurring, insert next occurrence and return it."""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    membership = _get_membership(session, auth.person_id, task.group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    task.done = True
    task.updated_at = datetime.utcnow()
    session.add(task)

    next_task: Task | None = None
    if task.rrule is not None:
        next_due_at = _compute_next_occurrence(task.rrule, task.due_at)
        if next_due_at is not None:
            next_task = Task(
                group_id=task.group_id,
                assignee_id=task.assignee_id,
                title=task.title,
                rrule=task.rrule,
                done=False,
                due_at=next_due_at,
            )
            session.add(next_task)

    session.commit()
    session.refresh(task)
    if next_task is not None:
        session.refresh(next_task)

    return DoneResponse(
        task=_task_to_response(task),
        next_occurrence=_task_to_response(next_task) if next_task else None,
    )


@router.delete("/tasks/{task_id}/done", response_model=TaskResponse)
def undo_task_done(
    task_id: uuid.UUID,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> TaskResponse:
    """Toggle task back to done=FALSE."""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    membership = _get_membership(session, auth.person_id, task.group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    task.done = False
    task.updated_at = datetime.utcnow()
    session.add(task)
    session.commit()
    session.refresh(task)
    return _task_to_response(task)
