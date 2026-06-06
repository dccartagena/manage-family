import uuid
from datetime import date, datetime

from sqlalchemy import JSON, CheckConstraint, text
from sqlmodel import Column, Field, SQLModel


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
        sa_column=Column(JSON, nullable=False, server_default=text("'{}'")),
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
    parent_group_id: uuid.UUID | None = Field(
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
    expires_at: datetime | None = Field(default=None, nullable=True)
    max_uses: int | None = Field(default=None, nullable=True, gt=0)
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
    assignee_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="persons.id",
        nullable=True,
    )
    title: str = Field(nullable=False)
    rrule: str | None = Field(default=None, nullable=True)
    done: bool = Field(
        default=False,
        nullable=False,
        sa_column_kwargs={"server_default": text("FALSE")},
    )
    due_at: datetime | None = Field(default=None, nullable=True)
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
    canonical_product_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="canonical_products.id",
        nullable=True,
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


class CanonicalProduct(SQLModel, table=True):
    __tablename__ = "canonical_products"
    __table_args__ = (
        CheckConstraint(
            "usual_location IN ('fridge','freezer','pantry','other')",
            name="ck_canonical_products_location",
        ),
        CheckConstraint("expiry_days_default > 0", name="ck_canonical_products_expiry_days"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    group_id: uuid.UUID = Field(foreign_key="groups.id", nullable=False)
    name: str = Field(nullable=False)
    category: str = Field(nullable=False)
    is_staple: bool = Field(
        default=False,
        nullable=False,
        sa_column_kwargs={"server_default": text("FALSE")},
    )
    usual_location: str = Field(nullable=False)
    expiry_days_default: int | None = Field(default=None, nullable=True)


class ProductCache(SQLModel, table=True):
    __tablename__ = "product_cache"
    __table_args__ = (
        CheckConstraint(
            "source IN ('off','ah','jumbo','manual')",
            name="ck_product_cache_source",
        ),
    )

    barcode: str = Field(primary_key=True)
    canonical_product_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="canonical_products.id",
        nullable=True,
    )
    source: str = Field(nullable=False)
    name: str = Field(nullable=False)
    brand: str | None = Field(default=None, nullable=True)
    category: str | None = Field(default=None, nullable=True)
    raw_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default=text("'{}'")),
    )
    cached_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )


class InventoryItem(SQLModel, table=True):
    __tablename__ = "inventory_items"
    __table_args__ = (
        CheckConstraint(
            "location IN ('fridge','freezer','pantry','other')",
            name="ck_inventory_items_location",
        ),
        CheckConstraint(
            "status IN ('ok','low','out')",
            name="ck_inventory_items_status",
        ),
        CheckConstraint(
            "removed_reason IN ('used','thrown','transferred')",
            name="ck_inventory_items_removed_reason",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    group_id: uuid.UUID = Field(foreign_key="groups.id", nullable=False)
    canonical_product_id: uuid.UUID = Field(
        foreign_key="canonical_products.id",
        nullable=False,
    )
    barcode: str | None = Field(
        default=None,
        foreign_key="product_cache.barcode",
        nullable=True,
    )
    name: str = Field(nullable=False)
    location: str = Field(nullable=False)
    status: str = Field(
        default="ok",
        nullable=False,
        sa_column_kwargs={"server_default": text("'ok'")},
    )
    expiry_date: date | None = Field(default=None, nullable=True)
    added_by: uuid.UUID = Field(foreign_key="persons.id", nullable=False)
    added_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )
    removed_at: datetime | None = Field(default=None, nullable=True)
    removed_reason: str | None = Field(default=None, nullable=True)


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
    rrule: str | None = Field(default=None, nullable=True)
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
