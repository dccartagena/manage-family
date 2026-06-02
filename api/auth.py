import os
import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt


@dataclass(frozen=True)
class PersonAuth:
    person_id: uuid.UUID
    email: str


def _get_jwt_secret() -> str:
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise RuntimeError("SUPABASE_JWT_SECRET env var is not set")
    return secret


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
        return jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
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
