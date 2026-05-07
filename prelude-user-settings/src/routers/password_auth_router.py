"""
Password Authentication Router
==============================
Handles username+password authentication for users who don't use OAuth.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, validator
from typing import Optional
import logging
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
import secrets

from service_core.db import get_pool_manager
from services.employee_sync import sync_user_to_employee_info
from config.settings import JWT_SECRET

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(...)
    email: Optional[str] = Field(None)

    @validator('username')
    def validate_username(cls, v):
        if '@' in v:
            raise ValueError('Username cannot contain @ symbol')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v.lower()

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    success: bool
    id_token: str
    refresh_token: str
    expires_in: int
    user_info: dict


def generate_jwt_token(user_data: dict) -> str:
    payload = {
        "email": user_data['email'],
        "name": user_data.get('name', user_data['username']),
        "username": user_data['username'],
        "company": user_data.get('company', user_data['username']),
        "role": user_data.get('role', 'user'),
        "db_name": user_data.get('db_name', 'prelude_visitor'),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def generate_refresh_token(user_email: str) -> str:
    payload = {
        "email": user_email,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post("/register", response_model=AuthResponse)
async def register_user(request: RegisterRequest):
    """Register a new user with username and password."""
    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        # Rate limiting
        last_reg = await conn.fetchrow(
            "SELECT created_at FROM user_profiles WHERE created_at IS NOT NULL ORDER BY created_at DESC LIMIT 1"
        )
        if last_reg and last_reg['created_at']:
            last_time = last_reg['created_at']
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            diff = (datetime.now(timezone.utc) - last_time).total_seconds()
            if diff < 30:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Registration rate limit exceeded. Wait {int(30 - diff)} seconds."
                )

        existing_username = await conn.fetchval(
            "SELECT email FROM user_profiles WHERE username = $1", request.username
        )
        if existing_username:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

        if request.email:
            email = request.email
            has_real_email = True
            existing_email = await conn.fetchval(
                "SELECT email FROM user_profiles WHERE email = $1", email
            )
            if existing_email:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        else:
            email = f"{request.username}@prelude.local"
            has_real_email = False
            existing_email = await conn.fetchval(
                "SELECT email FROM user_profiles WHERE email = $1", email
            )
            if existing_email:
                email = f"{request.username}.{secrets.token_hex(4)}@prelude.local"

        password_hash = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user_db_name = "prelude_visitor"

        user = await conn.fetchrow(
            """
            INSERT INTO user_profiles
            (email, username, password_hash, has_real_email, name, company, role, db_name, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING email, username, name, company, role, db_name
            """,
            email, request.username, password_hash, has_real_email,
            request.username, request.username, 'user', user_db_name,
            datetime.now(timezone.utc).replace(tzinfo=None)
        )

    user_dict = dict(user)
    await sync_user_to_employee_info(user_dict)

    id_token = generate_jwt_token(user_dict)
    refresh_token = generate_refresh_token(user_dict['email'])

    logger.info(f"User registered: {request.username} ({email})")

    return AuthResponse(
        success=True,
        id_token=id_token,
        refresh_token=refresh_token,
        expires_in=JWT_EXPIRATION_HOURS * 3600,
        user_info={
            "email": user_dict['email'],
            "username": user_dict['username'],
            "name": user_dict['name'],
            "company": user_dict['company'],
            "role": user_dict['role'],
            "has_real_email": has_real_email
        }
    )


@router.post("/login-password", response_model=AuthResponse)
async def login_with_password(request: LoginRequest):
    """Login with username and password."""
    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT email, username, password_hash, name, company, role, db_name, has_real_email
            FROM user_profiles WHERE LOWER(username) = LOWER($1)
            """,
            request.username
        )

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Username does not exist")

    if not user['password_hash']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account uses OAuth login. Please use Google or Microsoft sign-in."
        )

    if not bcrypt.checkpw(request.password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

    user_dict = dict(user)
    await sync_user_to_employee_info(user_dict)

    id_token = generate_jwt_token(user_dict)
    refresh_token = generate_refresh_token(user_dict['email'])

    logger.info(f"User logged in: {user_dict['username']} ({user_dict['email']})")

    return AuthResponse(
        success=True,
        id_token=id_token,
        refresh_token=refresh_token,
        expires_in=JWT_EXPIRATION_HOURS * 3600,
        user_info={
            "email": user_dict['email'],
            "username": user_dict['username'],
            "name": user_dict['name'],
            "company": user_dict['company'],
            "role": user_dict['role'],
            "has_real_email": user_dict['has_real_email']
        }
    )


@router.post("/check-username")
async def check_username_availability(username: str):
    """Check if a username is available."""
    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM user_profiles WHERE LOWER(username) = LOWER($1)", username
        )
    return {"username": username, "available": count == 0}
