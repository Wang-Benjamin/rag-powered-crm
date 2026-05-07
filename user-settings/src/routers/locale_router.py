"""
User Locale Router
==================
Handles user locale preference (preferred_locale).
Reads/writes to user_profiles in prelude_user_analytics DB.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import logging

from service_core.auth import verify_auth_token
from service_core.db import get_pool_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile")

SUPPORTED_LOCALES = ['en', 'zh-CN']
DEFAULT_LOCALE = 'en'


class LocaleResponse(BaseModel):
    preferred_locale: str


class LocaleUpdateRequest(BaseModel):
    preferred_locale: str


def parse_accept_language(header: str | None) -> str | None:
    """Parse Accept-Language header and return best matching supported locale."""
    if not header:
        return None

    parts = []
    for part in header.split(','):
        segments = part.strip().split(';q=')
        lang = segments[0].strip()
        try:
            q = float(segments[1]) if len(segments) > 1 else 1.0
        except (ValueError, IndexError):
            q = 0.0
        parts.append((lang, q))

    parts.sort(key=lambda x: x[1], reverse=True)

    for lang, _ in parts:
        if lang in SUPPORTED_LOCALES:
            return lang
        prefix = lang.split('-')[0]
        for supported in SUPPORTED_LOCALES:
            if supported.lower().startswith(prefix.lower()):
                return supported

    return None


@router.get("/locale", response_model=LocaleResponse)
async def get_locale(
    request: Request,
    authenticated_user: dict = Depends(verify_auth_token)
):
    """Get locale preference for authenticated user. Auto-detects on first access."""
    user_email = authenticated_user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT preferred_locale FROM user_profiles WHERE email = $1", user_email
        )

        if not row:
            raise HTTPException(status_code=404, detail="User profile not found")

        locale = row.get('preferred_locale')

        if locale is None:
            x_locale = request.headers.get('x-user-locale')
            if x_locale and x_locale in SUPPORTED_LOCALES:
                detected = x_locale
            else:
                accept_lang = request.headers.get('accept-language')
                detected = parse_accept_language(accept_lang) or DEFAULT_LOCALE
            await conn.execute(
                "UPDATE user_profiles SET preferred_locale = $1 WHERE email = $2",
                detected, user_email
            )
            locale = detected

        return LocaleResponse(preferred_locale=locale)


@router.put("/locale", response_model=LocaleResponse)
async def update_locale(
    body: LocaleUpdateRequest,
    authenticated_user: dict = Depends(verify_auth_token)
):
    """Update locale preference for authenticated user."""
    user_email = authenticated_user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    if body.preferred_locale not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported locale: {body.preferred_locale}. Supported: {SUPPORTED_LOCALES}"
        )

    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE user_profiles SET preferred_locale = $1 WHERE email = $2 RETURNING preferred_locale",
            body.preferred_locale, user_email
        )
        if not row:
            raise HTTPException(status_code=404, detail="User profile not found")

        return LocaleResponse(preferred_locale=row['preferred_locale'] or DEFAULT_LOCALE)
