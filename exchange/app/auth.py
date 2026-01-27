"""Authentication for trader endpoints."""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Account
from app.services.admin import hash_api_key

# API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_account(
    api_key: str | None = Security(api_key_header),
    session: AsyncSession = Depends(get_session),
) -> Account:
    """Validate API key and return the associated account.

    Args:
        api_key: API key from X-API-Key header
        session: Database session

    Returns:
        The authenticated account

    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Hash the provided key and look up the account
    key_hash = hash_api_key(api_key)
    result = await session.execute(
        select(Account).where(Account.api_key_hash == key_hash)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return account
