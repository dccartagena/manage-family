import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Column, Field, SQLModel
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB


class Person(SQLModel, table=True):
    __tablename__ = "persons"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    email: str = Field(nullable=False, unique=True)
    display_name: str = Field(nullable=False)
    ui_prefs: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'")),
    )
    ical_secret: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        nullable=False,
        unique=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )


class Group(SQLModel, table=True):
    __tablename__ = "groups"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    parent_group_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="groups.id",
        nullable=True,
    )
    name: str = Field(nullable=False)
    depth: int = Field(
        default=0,
        nullable=False,
        ge=0,
        le=4,
        sa_column_kwargs={"server_default": text("0")},
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )


class Membership(SQLModel, table=True):
    __tablename__ = "memberships"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    person_id: uuid.UUID = Field(foreign_key="persons.id", nullable=False)
    group_id: uuid.UUID = Field(foreign_key="groups.id", nullable=False)
    role: str = Field(nullable=False)
    joined_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )


class Invite(SQLModel, table=True):
    __tablename__ = "invites"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    group_id: uuid.UUID = Field(foreign_key="groups.id", nullable=False)
    created_by: uuid.UUID = Field(foreign_key="persons.id", nullable=False)
    token: str = Field(
        nullable=False,
        unique=True,
        sa_column_kwargs={"server_default": text("encode(gen_random_bytes(32), 'hex')")},
    )
    expires_at: Optional[datetime] = Field(default=None, nullable=True)
    max_uses: Optional[int] = Field(default=None, nullable=True, gt=0)
    uses: int = Field(
        default=0,
        nullable=False,
        sa_column_kwargs={"server_default": text("0")},
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    group_id: uuid.UUID = Field(foreign_key="groups.id", nullable=False)
    assignee_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="persons.id",
        nullable=True,
    )
    title: str = Field(nullable=False)
    rrule: Optional[str] = Field(default=None, nullable=True)
    done: bool = Field(
        default=False,
        nullable=False,
        sa_column_kwargs={"server_default": text("FALSE")},
    )
    due_at: Optional[datetime] = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )


class ShoppingItem(SQLModel, table=True):
    __tablename__ = "shopping_items"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    group_id: uuid.UUID = Field(foreign_key="groups.id", nullable=False)
    name: str = Field(nullable=False)
    checked: bool = Field(
        default=False,
        nullable=False,
        sa_column_kwargs={"server_default": text("FALSE")},
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    group_id: uuid.UUID = Field(foreign_key="groups.id", nullable=False)
    title: str = Field(nullable=False)
    starts_at: datetime = Field(nullable=False)
    rrule: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )


class Reminder(SQLModel, table=True):
    __tablename__ = "reminders"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    person_id: uuid.UUID = Field(foreign_key="persons.id", nullable=False)
    title: str = Field(nullable=False)
    fire_at: datetime = Field(nullable=False)
    delivered: bool = Field(
        default=False,
        nullable=False,
        sa_column_kwargs={"server_default": text("FALSE")},
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )
