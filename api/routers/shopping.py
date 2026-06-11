import uuid
from datetime import datetime
from typing import Annotated

from api.auth import PersonAuth, get_person_auth
from api.db import get_session
from api.models import CanonicalProduct, InventoryItem, Membership, ShoppingItem
from api.routers.inventory import InventoryItemRead, _inventory_item_to_read
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

router = APIRouter()


class ShoppingItemCreate(BaseModel):
    name: str

    model_config = {"extra": "forbid"}


class ShoppingItemUpdate(BaseModel):
    name: str | None = None
    checked: bool | None = None

    model_config = {"extra": "forbid"}


class ShoppingItemResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    name: str
    checked: bool
    canonical_product_id: uuid.UUID | None = None
    updated_at: datetime


class LoopCloseRequest(BaseModel):
    shopping_item_ids: list[uuid.UUID] = Field(min_length=1)

    model_config = {"extra": "forbid"}


class LoopCloseResponse(BaseModel):
    created: list[InventoryItemRead]
    skipped: list[uuid.UUID]


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


def _item_to_response(item: ShoppingItem) -> ShoppingItemResponse:
    return ShoppingItemResponse(
        id=item.id,
        group_id=item.group_id,
        name=item.name,
        checked=item.checked,
        canonical_product_id=item.canonical_product_id,
        updated_at=item.updated_at,
    )


@router.get("/groups/{group_id}/shopping", response_model=list[ShoppingItemResponse])
def list_shopping_items(
    group_id: uuid.UUID,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ShoppingItemResponse]:
    membership = _get_membership(session, auth.person_id, group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    items = session.exec(select(ShoppingItem).where(ShoppingItem.group_id == group_id)).all()
    return [_item_to_response(i) for i in items]


@router.post(
    "/groups/{group_id}/shopping",
    response_model=ShoppingItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_shopping_item(
    group_id: uuid.UUID,
    body: ShoppingItemCreate,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> ShoppingItemResponse:
    membership = _get_membership(session, auth.person_id, group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    item = ShoppingItem(
        group_id=group_id,
        name=body.name,
        checked=False,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return _item_to_response(item)


@router.patch("/shopping/{item_id}", response_model=ShoppingItemResponse)
def patch_shopping_item(
    item_id: uuid.UUID,
    body: ShoppingItemUpdate,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> ShoppingItemResponse:
    item = session.get(ShoppingItem, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopping item not found",
        )

    membership = _get_membership(session, auth.person_id, item.group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    # Server always sets updated_at — last-write-wins arbiter; client must not set it
    item.updated_at = datetime.utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return _item_to_response(item)


# ── T044: Shopping list loop-close ────────────────────────────────────────────


@router.post(
    "/groups/{group_id}/inventory/from-shopping",
    response_model=LoopCloseResponse,
    status_code=status.HTTP_201_CREATED,
)
def inventory_from_shopping(
    group_id: uuid.UUID,
    body: LoopCloseRequest,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> LoopCloseResponse:
    membership = _get_membership(session, auth.person_id, group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    created: list[InventoryItemRead] = []
    new_items: list[tuple[InventoryItem, str]] = []
    skipped: list[uuid.UUID] = []

    for item_id in body.shopping_item_ids:
        shopping_item = session.get(ShoppingItem, item_id)
        # Items that can't be converted (unknown, foreign group, or never associated
        # with a canonical product) are skipped, not failed — partial success is fine
        if (
            not shopping_item
            or shopping_item.group_id != group_id
            or shopping_item.canonical_product_id is None
        ):
            skipped.append(item_id)
            continue

        canonical_product = session.get(CanonicalProduct, shopping_item.canonical_product_id)
        if not canonical_product:
            skipped.append(item_id)
            continue

        inventory_item = InventoryItem(
            group_id=group_id,
            canonical_product_id=canonical_product.id,
            name=canonical_product.name,
            location=canonical_product.usual_location,
            status="ok",
            added_by=auth.person_id,
        )
        session.add(inventory_item)
        new_items.append((inventory_item, canonical_product.name))

    session.commit()
    for inventory_item, cp_name in new_items:
        session.refresh(inventory_item)
        created.append(_inventory_item_to_read(inventory_item, cp_name))

    return LoopCloseResponse(created=created, skipped=skipped)


@router.delete("/shopping/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shopping_item(
    item_id: uuid.UUID,
    auth: Annotated[PersonAuth, Depends(get_person_auth)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    item = session.get(ShoppingItem, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopping item not found",
        )

    membership = _get_membership(session, auth.person_id, item.group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller is not a member of this group",
        )

    session.delete(item)
    session.commit()
