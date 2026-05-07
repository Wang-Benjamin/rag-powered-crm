"""Centralized configuration for email_core.

Replaces scattered os.getenv() calls across delivery, sync, generation,
and translation files. Import `settings` from this module.
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmailCoreSettings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM — email generation (Anthropic Claude)
    anthropic_api_key: str = ""
    # OpenAI — used only for translation (gpt-5.4-nano is cheaper than Haiku)
    openai_api_key: str = ""

    # SMTP fallback
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Google OAuth (Gmail send + sync)
    google_client_id: str = ""
    google_client_secret: str = ""

    # Microsoft OAuth (Outlook send + sync)
    microsoft_tenant_id: str = "common"
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = "http://localhost:9000/auth/microsoft/callback"

    # Haiku — inbound email classification + writing style analysis (fast, cheap)
    classification_model: str = "claude-haiku-4-5-20251001"
    writing_style_model: str = "claude-haiku-4-5-20251001"

    # Translation models (OpenAI — cheaper than Haiku for translation)
    translation_interactive_model: str = "gpt-5.4-nano"
    translation_background_model: str = "gpt-5.4-nano"

    # Tracking / service URLs
    tracking_base_url: str = "http://localhost:8003"
    user_settings_url: str = "http://localhost:8005"


settings = EmailCoreSettings()
