from typing import Optional
import datetime

import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, PrimaryKeyConstraint, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class UserProfiles(Base):
    __tablename__ = 'user_profiles'
    __table_args__ = (
        PrimaryKeyConstraint('email', name='user_profiles_pkey'),
        UniqueConstraint('username', name='user_profiles_username_key'),
        Index('idx_user_profiles_username', 'username'),
        Index('ix_user_profiles_email', 'email'),
        {'schema': 'public'}
    )

    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    company: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    db_name: Mapped[Optional[str]] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(50))
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    has_real_email: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    preferred_locale: Mapped[Optional[str]] = mapped_column(String(10))
    onboarding_status: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'not_started'"))
    onboarding_step: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    onboarding_progress: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    onboarding_completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    outreach_alias: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    outreach_display_name: Mapped[Optional[str]] = mapped_column(String(255))
    wechat_openid: Mapped[Optional[str]] = mapped_column(String(64), unique=True)


class OutreachConversation(Base):
    __tablename__ = 'outreach_conversations'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='outreach_conversations_pkey'),
        Index('idx_outreach_conv_user', 'user_email'),
        Index('idx_outreach_conv_buyer', 'buyer_email'),
        {'schema': 'public'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    buyer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class OutreachMessage(Base):
    __tablename__ = 'outreach_messages'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='outreach_messages_pkey'),
        Index('idx_outreach_msg_conv', 'conversation_id'),
        Index('idx_outreach_msg_from', 'from_email'),
        Index('idx_outreach_msg_direction', 'direction'),
        {'schema': 'public'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey('outreach_conversations.id'), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # 'outbound' or 'inbound'
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    body_en: Mapped[Optional[str]] = mapped_column(Text)
    body_zh: Mapped[Optional[str]] = mapped_column(Text)
    message_id: Mapped[Optional[str]] = mapped_column(String(255))
    in_reply_to: Mapped[Optional[str]] = mapped_column(String(255))
    sendgrid_message_id: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class SmtpCredentials(Base):
    __tablename__ = 'smtp_credentials'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='smtp_credentials_pkey'),
        UniqueConstraint('user_email', name='smtp_credentials_user_email_key'),
        Index('idx_smtp_cred_user', 'user_email'),
        {'schema': 'public'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'custom'"))
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('587'))
    smtp_user: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    imap_host: Mapped[Optional[str]] = mapped_column(String(255))
    imap_port: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('993'))
    from_name: Mapped[Optional[str]] = mapped_column(String(255))
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class ActivityLog(Base):
    __tablename__ = 'activity_log'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='activity_log_pkey'),
        Index('idx_activity_log_user', 'user_id', 'created_at'),
        Index('idx_activity_log_resource', 'resource_type', 'resource_id'),
        Index('idx_activity_log_created', 'created_at'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class DealRoomTokens(Base):
    __tablename__ = 'deal_room_tokens'
    __table_args__ = (
        PrimaryKeyConstraint('share_token', name='deal_room_tokens_pkey'),
        UniqueConstraint('db_name', 'deal_id', name='deal_room_tokens_db_deal_key'),
        Index('idx_deal_room_tokens_db_deal', 'db_name', 'deal_id'),
        {'schema': 'public'}
    )

    share_token: Mapped[str] = mapped_column(String(32), primary_key=True)
    db_name: Mapped[str] = mapped_column(String(255), nullable=False)
    deal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    revoked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
