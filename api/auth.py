import os
import uuid
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
from fastapi import Header, HTTPException, status
from jose import JWTError, jwt


@dataclass(frozen=True)
class PersonAuth:
    person_id: uuid.UUID
    email: str


_jwks_cache: dict[str, Any] | None = None


def _get_jwt_secret() -> str:
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise RuntimeError("SUPABASE_JWT_SECRET env var is not set")
    return secret


def _load_jwks() -> dict[str, Any]:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    supabase_url = os.environ.get("SUPABASE_URL")
    if not supabase_url:
        raise RuntimeError("SUPABASE_URL env var is not set")
    resp = httpx.get(f"{supabase_url}/auth/v1/.well-known/jwks.json", timeout=5.0)
    resp.raise_for_status()
    _jwks_cache = {key["kid"]: key for key in resp.json().get("keys", [])}
    return _jwks_cache


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization.removeprefix("Bearer ")


def _decode_jwt(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
        if alg == "HS256":
            return jwt.decode(
                token,
                _get_jwt_secret(),
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        kid = header.get("kid")
        keys = _load_jwks()
        key = keys.get(kid) if kid else next(iter(keys.values()), None)
        if key is None:
            raise JWTError("No matching public key found in JWKS")
        return jwt.decode(token, key, algorithms=[alg], options={"verify_aud": False})
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_person_auth(
    authorization: Annotated[str | None, Header()] = None,
) -> PersonAuth:
    """FastAPI dependency returning person_id and email from a Supabase Bearer JWT."""
    token = _extract_bearer_token(authorization)
    payload = _decode_jwt(token)

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        person_id = uuid.UUID(str(sub))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sub claim is not a valid UUID",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    email = payload.get("email", "")
    return PersonAuth(person_id=person_id, email=email)


async def get_current_person(
    authorization: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    """FastAPI dependency returning person_id UUID from a Supabase Bearer JWT."""
    auth = await get_person_auth(authorization=authorization)
    return auth.person_id
