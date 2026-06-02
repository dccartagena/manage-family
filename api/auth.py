import os
import uuid
from typing import Annotated

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt


def _get_jwt_secret() -> str:
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise RuntimeError("SUPABASE_JWT_SECRET env var is not set")
    return secret


async def get_current_person(
    authorization: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    """FastAPI dependency that extracts and validates a Supabase Bearer JWT.

    Returns the person_id (sub claim) as a UUID.
    Raises HTTP 401 on missing, expired, or invalid token.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ")

    try:
        payload = jwt.decode(
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

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return uuid.UUID(str(sub))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sub claim is not a valid UUID",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
