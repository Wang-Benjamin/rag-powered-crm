"""
WeChat QR Code Login Router
============================
Handles WeChat scan-to-login via the Official Account (服务号) "带参数二维码" approach.

Flow:
1. Frontend requests a login QR code → backend creates a temporary parametric QR via WeChat API
2. User scans QR with WeChat → WeChat sends event to our webhook
3. Backend maps scene_id → wechat openid, checks if bound to a user
4. Frontend polls for status → gets JWT if bound, or "needs_bind" if not
5. If needs_bind: user enters username/password to bind, or creates new account
"""

import os
import time
import hashlib
import logging
import secrets
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from service_core.db import get_pool_manager
from routers.password_auth_router import generate_jwt_token, generate_refresh_token
from services.employee_sync import sync_user_to_employee_info
from config.settings import JWT_SECRET
import bcrypt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wechat")

# ── Config ──────────────────────────────────────────────────────────
WECHAT_APP_ID = os.getenv("WECHAT_APP_ID", "")
WECHAT_APP_SECRET = os.getenv("WECHAT_APP_SECRET", "")
WECHAT_TOKEN = os.getenv("WECHAT_TOKEN", "prelude_wx_2026")

# ── In-memory stores (use Redis in production for multi-instance) ──
_access_token_cache: Dict[str, Any] = {"token": None, "expires_at": 0}
_login_sessions: Dict[str, Dict[str, Any]] = {}  # scene_id → {status, openid, created_at, ...}
_openid_to_scene: Dict[str, str] = {}  # openid → scene_id (reverse lookup for text reply confirmation)


# ══════════════════════════════════════════════════════════════════════
# WeChat API helpers
# ══════════════════════════════════════════════════════════════════════

async def get_access_token() -> str:
    """Get or refresh the WeChat access_token (cached for ~2 hours)."""
    now = time.time()
    if _access_token_cache["token"] and _access_token_cache["expires_at"] > now + 60:
        return _access_token_cache["token"]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": WECHAT_APP_ID,
                "secret": WECHAT_APP_SECRET,
            },
        )
        data = resp.json()

    if "access_token" not in data:
        logger.error(f"Failed to get WeChat access_token: {data}")
        raise HTTPException(status_code=502, detail=f"WeChat API error: {data.get('errmsg', 'unknown')}")

    _access_token_cache["token"] = data["access_token"]
    _access_token_cache["expires_at"] = now + data.get("expires_in", 7200)
    logger.info("WeChat access_token refreshed")
    return data["access_token"]


async def create_temp_qr(scene_str: str, expire_seconds: int = 300) -> Dict[str, str]:
    """Create a temporary parametric QR code (valid for expire_seconds)."""
    token = await get_access_token()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"https://api.weixin.qq.com/cgi-bin/qrcode/create?access_token={token}",
            json={
                "expire_seconds": expire_seconds,
                "action_name": "QR_STR_SCENE",
                "action_info": {"scene": {"scene_str": scene_str}},
            },
        )
        data = resp.json()

    if "ticket" not in data:
        logger.error(f"Failed to create QR: {data}")
        raise HTTPException(status_code=502, detail="Failed to create WeChat QR code")

    ticket = data["ticket"]
    qr_url = f"https://mp.weixin.qq.com/cgi-bin/showqrcode?ticket={ticket}"
    return {"ticket": ticket, "qr_url": qr_url, "expire_seconds": expire_seconds}


async def get_wechat_user_info(openid: str) -> Dict[str, Any]:
    """Get WeChat user info (nickname, avatar, etc.)."""
    token = await get_access_token()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.weixin.qq.com/cgi-bin/user/info",
            params={"access_token": token, "openid": openid, "lang": "zh_CN"},
        )
        return resp.json()


def _build_text_reply(to_user: str, from_user: str, content: str) -> str:
    """Build a WeChat XML text reply message."""
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        "</xml>"
    )


async def _complete_login(session: Dict[str, Any], openid: str) -> None:
    """Check if openid is bound and update session accordingly."""
    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT email, username, name, company, role, db_name, has_real_email "
            "FROM user_profiles WHERE wechat_openid = $1",
            openid,
        )

    if user:
        user_dict = dict(user)
        id_token = generate_jwt_token(user_dict)
        refresh_token = generate_refresh_token(user_dict["email"])
        session["status"] = "bound"
        session["id_token"] = id_token
        session["refresh_token"] = refresh_token
        session["user_info"] = {
            "email": user_dict["email"],
            "username": user_dict["username"],
            "name": user_dict["name"],
            "company": user_dict["company"],
            "role": user_dict["role"],
        }
        logger.info(f"WeChat auto-login: {user_dict['email']}")
    else:
        wx_info = await get_wechat_user_info(openid)
        session["status"] = "needs_bind"
        session["wechat_nickname"] = wx_info.get("nickname", "")
        logger.info(f"WeChat needs bind: openid={openid}, nickname={session['wechat_nickname']}")


# ══════════════════════════════════════════════════════════════════════
# Pydantic models
# ══════════════════════════════════════════════════════════════════════

class QRLoginResponse(BaseModel):
    scene_id: str
    qr_url: str
    expire_seconds: int


class LoginStatusResponse(BaseModel):
    status: str  # "waiting" | "scanned" | "bound" | "needs_bind" — scanned = QR scanned, processing
    id_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    user_info: Optional[dict] = None
    wechat_nickname: Optional[str] = None


class BindAccountRequest(BaseModel):
    scene_id: str
    username: str
    password: str


class CreateAccountRequest(BaseModel):
    scene_id: str
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


# ══════════════════════════════════════════════════════════════════════
# Webhook — WeChat server verification & event handling
# ══════════════════════════════════════════════════════════════════════

def _verify_wechat_signature(signature: str, timestamp: str, nonce: str) -> bool:
    """Verify a WeChat-signed request. Returns True if signature matches the
    sha1(sorted(token, timestamp, nonce)) that WeChat sends on every callback.

    Used for both GET (URL verification) and POST (event push). Without this
    on POST, anyone who knows the callback URL could forge scan events with
    arbitrary openid/scene_id and bypass auth.
    """
    check_str = "".join(sorted([WECHAT_TOKEN, timestamp, nonce]))
    computed = hashlib.sha1(check_str.encode("utf-8")).hexdigest()
    return computed == signature


@router.get("/callback")
async def wechat_verify(
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(""),
):
    """WeChat server URL verification (GET request from WeChat)."""
    if _verify_wechat_signature(signature, timestamp, nonce):
        return Response(content=echostr, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Signature verification failed")


@router.post("/callback")
async def wechat_event(
    request: Request,
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
):
    """Handle WeChat push events (scan, subscribe, etc.)."""
    if not _verify_wechat_signature(signature, timestamp, nonce):
        logger.warning("WeChat POST callback signature verification failed")
        raise HTTPException(status_code=403, detail="Signature verification failed")

    body = await request.body()
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        logger.error("Invalid XML from WeChat")
        return Response(content="success", media_type="text/plain")

    msg_type = root.findtext("MsgType", "")
    event = root.findtext("Event", "")
    from_user = root.findtext("FromUserName", "")  # openid
    to_user = root.findtext("ToUserName", "")  # our official account
    event_key = root.findtext("EventKey", "")

    logger.info(f"WeChat event: type={msg_type}, event={event}, from={from_user}, key={event_key}")

    if msg_type == "event":
        # SCAN = already following, subscribe = new follower via QR
        if event in ("SCAN", "subscribe"):
            scene_id = event_key
            if event == "subscribe" and scene_id.startswith("qrscene_"):
                scene_id = scene_id[len("qrscene_"):]

            if scene_id and scene_id in _login_sessions:
                session = _login_sessions[scene_id]
                session["openid"] = from_user
                session["scan_time"] = datetime.now(timezone.utc)
                session["status"] = "scanned"
                _openid_to_scene[from_user] = scene_id

                # Reply asking user to confirm login
                reply = _build_text_reply(
                    from_user, to_user,
                    "您正在登录 Prelude 平台，回复「是」确认登录。"
                )
                logger.info(f"WeChat scan detected, awaiting confirmation: openid={from_user}, scene={scene_id}")
                return Response(content=reply, media_type="application/xml")

    elif msg_type == "text":
        content = (root.findtext("Content", "") or "").strip()
        # Check if this is a login confirmation reply
        if content in ("是", "yes", "Yes", "YES", "y", "Y", "确认"):
            scene_id = _openid_to_scene.get(from_user)
            if scene_id and scene_id in _login_sessions:
                session = _login_sessions[scene_id]
                if session.get("status") == "scanned" and session.get("openid") == from_user:
                    await _complete_login(session, from_user)
                    _openid_to_scene.pop(from_user, None)

                    if session["status"] == "bound":
                        reply_text = "✅ 登录成功！"
                    else:
                        reply_text = "✅ 扫码成功，请在网页上绑定账号。"

                    reply = _build_text_reply(from_user, to_user, reply_text)
                    logger.info(f"WeChat login confirmed: openid={from_user}")
                    return Response(content=reply, media_type="application/xml")

    # WeChat requires "success" response
    return Response(content="success", media_type="text/plain")


# ══════════════════════════════════════════════════════════════════════
# Login API endpoints
# ══════════════════════════════════════════════════════════════════════

@router.post("/qr/login", response_model=QRLoginResponse)
async def create_login_qr():
    """Generate a temporary QR code for WeChat scan login."""
    scene_id = f"login_{secrets.token_hex(8)}"
    qr_data = await create_temp_qr(scene_id, expire_seconds=300)

    _login_sessions[scene_id] = {
        "status": "waiting",
        "openid": None,
        "created_at": datetime.now(timezone.utc),
    }

    # Cleanup old sessions (>10 min)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    expired = [k for k, v in _login_sessions.items() if v["created_at"] < cutoff]
    for k in expired:
        openid = _login_sessions[k].get("openid")
        if openid:
            _openid_to_scene.pop(openid, None)
        del _login_sessions[k]

    return QRLoginResponse(
        scene_id=scene_id,
        qr_url=qr_data["qr_url"],
        expire_seconds=qr_data["expire_seconds"],
    )


@router.get("/qr/status/{scene_id}", response_model=LoginStatusResponse)
async def check_login_status(scene_id: str):
    """Poll this endpoint to check if the QR has been scanned."""
    session = _login_sessions.get(scene_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session expired or invalid")

    # Check expiry
    age = (datetime.now(timezone.utc) - session["created_at"]).total_seconds()
    if age > 600:
        del _login_sessions[scene_id]
        raise HTTPException(status_code=410, detail="Session expired")

    return LoginStatusResponse(
        status=session["status"],
        id_token=session.get("id_token"),
        refresh_token=session.get("refresh_token"),
        expires_in=24 * 3600 if session.get("id_token") else None,
        user_info=session.get("user_info"),
        wechat_nickname=session.get("wechat_nickname"),
    )


@router.post("/bind")
async def bind_wechat_to_existing(req: BindAccountRequest):
    """Bind WeChat openid to an existing account using username + password."""
    session = _login_sessions.get(req.scene_id)
    if not session or not session.get("openid"):
        raise HTTPException(status_code=400, detail="Invalid or expired session")

    openid = session["openid"]

    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        # Verify username + password
        user = await conn.fetchrow(
            "SELECT email, username, password_hash, name, company, role, db_name, has_real_email, wechat_openid "
            "FROM user_profiles WHERE LOWER(username) = LOWER($1)",
            req.username,
        )
        if not user:
            raise HTTPException(status_code=404, detail="Username does not exist")
        if not user["password_hash"]:
            raise HTTPException(status_code=400, detail="This account uses OAuth. Cannot bind via password.")
        if not bcrypt.checkpw(req.password.encode("utf-8"), user["password_hash"].encode("utf-8")):
            raise HTTPException(status_code=401, detail="Incorrect password")

        # Check if this WeChat is already bound to a different account
        existing = await conn.fetchval(
            "SELECT email FROM user_profiles WHERE wechat_openid = $1", openid
        )
        if existing and existing != user["email"]:
            raise HTTPException(status_code=409, detail="This WeChat is already bound to another account")

        # Check if the target account already has a different WeChat bound
        if user["wechat_openid"] and user["wechat_openid"] != openid:
            raise HTTPException(status_code=409, detail="This account is already bound to another WeChat")

        # Bind
        await conn.execute(
            "UPDATE user_profiles SET wechat_openid = $1 WHERE email = $2",
            openid, user["email"],
        )

    user_dict = dict(user)
    await sync_user_to_employee_info(user_dict)

    id_token = generate_jwt_token(user_dict)
    refresh_token = generate_refresh_token(user_dict["email"])

    # Update session so polling picks it up
    session["status"] = "bound"
    session["id_token"] = id_token
    session["refresh_token"] = refresh_token
    session["user_info"] = {
        "email": user_dict["email"],
        "username": user_dict["username"],
        "name": user_dict["name"],
        "company": user_dict["company"],
        "role": user_dict["role"],
    }

    logger.info(f"WeChat bound to existing account: {user_dict['email']}")

    return {
        "success": True,
        "id_token": id_token,
        "refresh_token": refresh_token,
        "expires_in": 24 * 3600,
        "user_info": session["user_info"],
    }


@router.post("/register")
async def register_and_bind_wechat(req: CreateAccountRequest):
    """Create a new account and bind WeChat openid to it."""
    session = _login_sessions.get(req.scene_id)
    if not session or not session.get("openid"):
        raise HTTPException(status_code=400, detail="Invalid or expired session")

    openid = session["openid"]

    # Validate username
    if "@" in req.username:
        raise HTTPException(status_code=400, detail="Username cannot contain @")
    if not req.username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Username can only contain letters, numbers, underscores, and hyphens")
    username = req.username.lower()

    pm = get_pool_manager()
    pool = await pm.get_analytics_pool()
    async with pool.acquire() as conn:
        # Check username availability
        existing = await conn.fetchval(
            "SELECT email FROM user_profiles WHERE username = $1", username
        )
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")

        # Check openid not already bound
        existing_wx = await conn.fetchval(
            "SELECT email FROM user_profiles WHERE wechat_openid = $1", openid
        )
        if existing_wx:
            raise HTTPException(status_code=409, detail="This WeChat is already bound to an account")

        email = f"{username}@prelude.local"
        existing_email = await conn.fetchval(
            "SELECT email FROM user_profiles WHERE email = $1", email
        )
        if existing_email:
            email = f"{username}.{secrets.token_hex(4)}@prelude.local"

        password_hash = bcrypt.hashpw(req.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        user = await conn.fetchrow(
            """
            INSERT INTO user_profiles
            (email, username, password_hash, has_real_email, name, company, role, db_name, wechat_openid, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING email, username, name, company, role, db_name
            """,
            email, username, password_hash, False,
            username, username, "user", "prelude_visitor", openid,
            datetime.now(timezone.utc).replace(tzinfo=None),
        )

    user_dict = dict(user)
    await sync_user_to_employee_info(user_dict)

    id_token = generate_jwt_token(user_dict)
    refresh_token = generate_refresh_token(user_dict["email"])

    session["status"] = "bound"
    session["id_token"] = id_token
    session["refresh_token"] = refresh_token
    session["user_info"] = {
        "email": user_dict["email"],
        "username": user_dict["username"],
        "name": user_dict["name"],
        "company": user_dict["company"],
        "role": user_dict["role"],
    }

    logger.info(f"New account created via WeChat: {user_dict['email']}")

    return {
        "success": True,
        "id_token": id_token,
        "refresh_token": refresh_token,
        "expires_in": 24 * 3600,
        "user_info": session["user_info"],
    }
