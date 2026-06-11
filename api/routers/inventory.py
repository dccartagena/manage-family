import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from api.auth import PersonAuth, get_person_auth
from api.db import get_session
from api.models import CanonicalProduct, InventoryItem, Membership, ProductCache, ShoppingItem
from api.services.product_lookup import ProductLookupService
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

router = APIRouter(tags=["inventory"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class ProductLookupResult(BaseModel):
    barcode: str
    name: str
    brand: str | None
    category: str | None
    source: Literal["off", "ah", "jumbo", "manual"]
    canonical_product_id: uuid.UUID | None
    canonical_product_name: str | None


class CanonicalProductRead(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    name: str
    category: str
    is_staple: bool
    usual_location: Literal["fridge", "freezer", "pantry", "other"]
    expiry_days_default: int | None


class CanonicalProductCreate(BaseModel):
    name: str
    category: str
    is_staple: bool
    usual_location: Literal["fridge", "freezer", "pantry", "other"]
    expiry_days_default: int | None = None

    model_config = {"extra": "forbid"}


class CanonicalProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    is_staple: bool | None = None
    usual_location: Literal["fridge", "freezer", "pantry", "other"] | None = None
    expiry_days_default: int | None = None

    model_config = {"extra": "forbid"}


class InventoryItemRead(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    canonical_product_id: uuid.UUID
    canonical_product_name: str
    barcode: str | None
    name: str
    location: Literal["fridge", "freezer", "pantry", "other"]
    status: Literal["ok", "low", "out"]
    expiry_date: str | None
    added_by: uuid.UUID
    added_at: datetime


class InventoryItemCreate(BaseModel):
    canonical_product_id: uuid.UUID
    barcode: str | None = None
    name: str
    location: Literal["fridge", "freezer", "pantry", "other"]
    expiry_date: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("expiry_date")
    @classmethod
    def validate_expiry_date_format(cls, v: str | None) -> str | None:
        if v is None:
            return None
        try:
            datetime.strptime(v, "%d-%m-%Y")
        except ValueError as err:
            raise ValueError("expiry_date must be in DD-MM-YYYY format") from err
        return v


class InventoryItemUpdate(BaseModel):
    status: Literal["ok", "low", "out"] | None = None
    expiry_date: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("expiry_date")
    @classmethod
    def validate_expiry_date_format(cls, v: str | None) -> str | None:
        if v is None:
            return None
        try:
            datetime.strptime(v, "%d-%m-%Y")
        except ValueError as err:
            raise ValueError("expiry_date must be in DD-MM-YYYY format") from err
        return v


class InventoryItemUpdateResponse(InventoryItemRead):
    shopping_item_created: bool
    shopping_item_name: str | None


class RemoveInventoryItemRequest(BaseModel):
    removed_reason: Literal["used", "thrown", "transferred"]

    model_config = {"extra": "forbid"}


# ── Helpers ───────────────────────────────────────────────────────────────────


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


def _canonical_product_to_read(cp: CanonicalProduct) -> CanonicalProductRead:
    return CanonicalProductRead(
        id=cp.id,
        group_id=cp.group_id,
        name=cp.name,
        category=cp.category,
        is_staple=cp.is_staple,
        usual_location=cp.usual_location,
        expiry_days_default=cp.expiry_days_default,
    )


def _inventory_item_to_read(
    item: InventoryItem,
    canonical_product_name: str,
) -> InventoryItemRead:
    expiry_date_str = item.expiry_date.strftime("%d-%m-%Y") if item.expiry_date else None
    return InventoryItemRead(
        id=item.id,
        group_id=item.group_id,
        canonical_product_id=item.canonical_product_id,
        canonical_product_name=canonical_product_name,
        barcode=item.barcode,
        name=item.name,
        location=item.location,
        status=item.status,
        expiry_date=expiry_date_str,
        added_by=item.added_by,
        added_at=item.added_at,
    )


# ── T019: Product lookup endpoint ─────────────────────────────────────────────


@router.get("/inventory/product/{barcode}", response_model=ProductLookupResult)
def lookup_product(
    barcode: str,
    session: Annotated[Session, Depends(get_session)],
) -> ProductLookupResult:
    service = ProductLookupService(session)
    cache_entry = service.lookup_barcode(barcode)

    canonical_product_name: str | None = None
    if cache_entry.canonical_product_id:
        cp = session.get(CanonicalProduct, cache_entry.canonical_product_id)
        if cp:
            canonical_product_name = cp.name

    return ProductLookupResult(
        barcode=cache_entry.barcode,
        name=cache_entry.name,
        brand=cache_entry.brand,
        category=cache_entry.category,
        source=cache_entry.source,
        canonical_product_id=cache_entry.canonical_product_id,
        canonical_product_name=canonical_product_name,
    )


# ── T020: Canonical products list + create ────────────────────────────────────


@router.get(
    "/groups/{group_id}/canonical-products",
    response_model=list[CanonicalProductRead],
)
def list_canonical_products(
    group_id: uuid.UUID,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> list[CanonicalProductRead]:
    membership = _get_membership(session, auth.person_id, group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    products = session.exec(
        select(CanonicalProduct).where(CanonicalProduct.group_id == group_id)
    ).all()
    return [_canonical_product_to_read(p) for p in products]


@router.post(
    "/groups/{group_id}/canonical-products",
    response_model=CanonicalProductRead,
    status_code=status.HTTP_201_CREATED,
)
def create_canonical_product(
    group_id: uuid.UUID,
    body: CanonicalProductCreate,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> CanonicalProductRead:
    membership = _get_membership(session, auth.person_id, group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    product = CanonicalProduct(
        group_id=group_id,
        name=body.name,
        category=body.category,
        is_staple=body.is_staple,
        usual_location=body.usual_location,
        expiry_days_default=body.expiry_days_default,
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    return _canonical_product_to_read(product)


# ── T021: Canonical product update ────────────────────────────────────────────


@router.patch(
    "/canonical-products/{canonical_product_id}",
    response_model=CanonicalProductRead,
)
def update_canonical_product(
    canonical_product_id: uuid.UUID,
    body: CanonicalProductUpdate,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> CanonicalProductRead:
    product = session.get(CanonicalProduct, canonical_product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canonical product not found",
        )

    membership = _get_membership(session, auth.person_id, product.group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    session.add(product)
    session.commit()
    session.refresh(product)
    return _canonical_product_to_read(product)


# ── T022: Inventory item create ───────────────────────────────────────────────


@router.post(
    "/groups/{group_id}/inventory",
    response_model=InventoryItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_inventory_item(
    group_id: uuid.UUID,
    body: InventoryItemCreate,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> InventoryItemRead:
    membership = _get_membership(session, auth.person_id, group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    canonical_product = session.get(CanonicalProduct, body.canonical_product_id)
    if not canonical_product or canonical_product.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canonical product not found in this group",
        )

    expiry_date: date | None = None
    if body.expiry_date:
        expiry_date = datetime.strptime(body.expiry_date, "%d-%m-%Y").date()

    item = InventoryItem(
        group_id=group_id,
        canonical_product_id=body.canonical_product_id,
        barcode=body.barcode,
        name=body.name,
        location=body.location,
        status="ok",
        expiry_date=expiry_date,
        added_by=auth.person_id,
    )
    session.add(item)

    # Update product_cache.canonical_product_id on first association for this barcode
    if body.barcode:
        cache_entry = session.get(ProductCache, body.barcode)
        if cache_entry and cache_entry.canonical_product_id is None:
            cache_entry.canonical_product_id = body.canonical_product_id
            session.add(cache_entry)

    session.commit()
    session.refresh(item)
    return _inventory_item_to_read(item, canonical_product.name)


# ── T029: Inventory list ──────────────────────────────────────────────────────


@router.get(
    "/groups/{group_id}/inventory",
    response_model=list[InventoryItemRead],
)
def list_inventory(
    group_id: uuid.UUID,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> list[InventoryItemRead]:
    membership = _get_membership(session, auth.person_id, group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    items = session.exec(
        select(InventoryItem).where(
            InventoryItem.group_id == group_id,
            InventoryItem.removed_at.is_(None),  # type: ignore[union-attr]
        )
    ).all()

    result: list[InventoryItemRead] = []
    for item in items:
        cp = session.get(CanonicalProduct, item.canonical_product_id)
        cp_name = cp.name if cp else ""
        result.append(_inventory_item_to_read(item, cp_name))
    return result


# ── T030: Inventory item status/expiry update ─────────────────────────────────


@router.patch(
    "/inventory/{item_id}",
    response_model=InventoryItemUpdateResponse,
)
def update_inventory_item(
    item_id: uuid.UUID,
    body: InventoryItemUpdate,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> InventoryItemUpdateResponse:
    item = session.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )

    membership = _get_membership(session, auth.person_id, item.group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    if body.status is not None:
        item.status = body.status

    if body.expiry_date is not None:
        item.expiry_date = datetime.strptime(body.expiry_date, "%d-%m-%Y").date()

    session.add(item)

    cp = session.get(CanonicalProduct, item.canonical_product_id)

    # T034: staple auto-add — status→low on a staple puts it on the shopping list,
    # unless an unchecked entry for the same canonical product already exists
    shopping_item_created = False
    shopping_item_name: str | None = None
    if body.status == "low" and cp and cp.is_staple:
        existing = session.exec(
            select(ShoppingItem).where(
                ShoppingItem.group_id == item.group_id,
                ShoppingItem.canonical_product_id == cp.id,
                ShoppingItem.checked == False,  # noqa: E712 — SQL expression, not identity
            )
        ).first()
        if not existing:
            session.add(
                ShoppingItem(
                    group_id=item.group_id,
                    name=cp.name,
                    checked=False,
                    canonical_product_id=cp.id,
                )
            )
            shopping_item_created = True
            shopping_item_name = cp.name

    session.commit()
    session.refresh(item)

    cp_name = cp.name if cp else ""
    base = _inventory_item_to_read(item, cp_name)
    return InventoryItemUpdateResponse(
        **base.model_dump(),
        shopping_item_created=shopping_item_created,
        shopping_item_name=shopping_item_name,
    )


# ── T039: Inventory item removal (soft delete) ────────────────────────────────


@router.delete("/inventory/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory_item(
    item_id: uuid.UUID,
    body: RemoveInventoryItemRequest,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    item = session.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )

    membership = _get_membership(session, auth.person_id, item.group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    item.removed_at = datetime.utcnow()
    item.removed_reason = body.removed_reason
    session.add(item)
    session.commit()
