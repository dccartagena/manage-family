from __future__ import annotations

import os

import httpx
from fastapi import HTTPException, status
from sqlmodel import Session

from api.models import ProductCache

_OFF_BASE_URL = os.environ.get("OPEN_FOOD_FACTS_URL", "https://world.openfoodfacts.org")
_OFF_TIMEOUT = 10.0

_OFF_CATEGORY_MAP: dict[str, str] = {
    "en:fresh-dairy": "fresh_dairy",
    "en:dairy": "fresh_dairy",
    "en:milks": "fresh_dairy",
    "en:yogurts": "fresh_dairy",
    "en:cheeses": "cheese",
    "en:eggs": "eggs",
    "en:fresh-meat": "raw_meat_fish",
    "en:fresh-fish": "raw_meat_fish",
    "en:fish": "raw_meat_fish",
    "en:fresh-pasta": "fresh_pasta",
    "en:fresh-vegetables": "fresh_produce",
    "en:fresh-fruits": "fresh_produce",
    "en:fruits": "fresh_produce",
    "en:vegetables": "fresh_produce",
    "en:frozen-foods": "frozen",
    "en:canned-foods": "canned_jarred",
    "en:jarred-foods": "canned_jarred",
    "en:cereals-and-their-products": "dry_goods",
    "en:pasta": "dry_goods",
    "en:rice": "dry_goods",
}


def _map_off_category(categories_tags: list[str]) -> str | None:
    for tag in categories_tags:
        if tag in _OFF_CATEGORY_MAP:
            return _OFF_CATEGORY_MAP[tag]
    return None


class ProductLookupService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def lookup_barcode(self, barcode: str) -> ProductCache:
        cached = self._session.get(ProductCache, barcode)
        if cached:
            return cached

        for fetch_fn in (self._fetch_from_off, self._fetch_from_ah, self._fetch_from_jumbo):
            try:
                result = fetch_fn(barcode)
            except NotImplementedError:
                continue
            if result is not None:
                self._session.add(result)
                self._session.commit()
                self._session.refresh(result)
                return result

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with barcode {barcode!r} not found in any source",
        )

    def _fetch_from_off(self, barcode: str) -> ProductCache | None:
        url = f"{_OFF_BASE_URL}/api/v2/product/{barcode}"
        try:
            response = httpx.get(url, timeout=_OFF_TIMEOUT)
        except httpx.HTTPError:
            return None

        if response.status_code == 404:
            return None

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            return None

        data = response.json()
        if data.get("status") != 1:
            return None

        product = data.get("product", {})
        name = product.get("product_name") or product.get("product_name_en", "")
        if not name:
            return None

        brand_raw: str | None = product.get("brands")
        brand = brand_raw.strip() if brand_raw else None

        return ProductCache(
            barcode=barcode,
            source="off",
            name=name,
            brand=brand or None,
            category=_map_off_category(product.get("categories_tags", [])),
            raw_data=data,
        )

    def _fetch_from_ah(self, barcode: str) -> ProductCache | None:  # noqa: ARG002
        raise NotImplementedError

    def _fetch_from_jumbo(self, barcode: str) -> ProductCache | None:  # noqa: ARG002
        raise NotImplementedError
