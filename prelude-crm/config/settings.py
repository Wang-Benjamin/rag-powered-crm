"""Configuration settings for CRM Service."""

import os
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Application settings
    APP_NAME: str = "Prelude CRM Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", "8003"))

    # Monitoring
    SENTRY_DSN: Optional[str] = None

    # Service URLs
    USER_SETTINGS_URL: str = os.getenv("USER_SETTINGS_URL", "http://localhost:8005")
    CRM_SERVICE_URL: str = os.getenv("CRM_SERVICE_URL", "http://localhost:8003")

    # Database settings - all required, no fallbacks for credentials
    SESSIONS_DB_HOST: Optional[str] = None
    SESSIONS_DB_PORT: Optional[int] = None
    SESSIONS_DB_USER: Optional[str] = None
    SESSIONS_DB_PASSWORD: Optional[str] = None
    SESSIONS_DB_NAME: Optional[str] = None

    @field_validator('SESSIONS_DB_PORT', 'MANAGEMENT_DB_PORT', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        if v == '' or v is None:
            return None
        return int(v)
    
    # Auth settings
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "test_client_id")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "test_client_secret")
    MICROSOFT_CLIENT_ID: Optional[str] = os.getenv("MICROSOFT_CLIENT_ID")
    MICROSOFT_CLIENT_SECRET: Optional[str] = os.getenv("MICROSOFT_CLIENT_SECRET")
    MICROSOFT_TENANT_ID: Optional[str] = os.getenv("MICROSOFT_TENANT_ID", "common")
    JWT_SECRET: str = ""

    @field_validator('JWT_SECRET', mode='after')
    @classmethod
    def jwt_secret_must_be_set(cls, v):
        if not v:
            raise ValueError("JWT_SECRET environment variable is not set")
        return v

    # AI settings
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    LITELLM_PARAMS: Optional[str] = os.getenv("LITELLM_PARAMS")

    # Agent settings
    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "openai")
    DEFAULT_OPENAI_MODEL: str = os.getenv("DEFAULT_OPENAI_MODEL", "gpt-4.1-mini")
    GPT_4_1_MINI_MODEL: str = os.getenv("GPT_4_1_MINI_MODEL", "gpt-4.1-mini")
    GPT_5_MINI_MODEL: str = os.getenv("GPT_5_MINI_MODEL", "gpt-5.4-mini")

    # RAG settings
    COHERE_API_KEY: Optional[str] = os.getenv("COHERE_API_KEY")

    # Email generation concurrency settings
    MAX_CONCURRENT_EMAIL_GENERATIONS: int = int(os.getenv("MAX_CONCURRENT_EMAIL_GENERATIONS", "10"))

    # SendGrid settings
    SENDGRID_API_KEY: Optional[str] = os.getenv("SENDGRID_API_KEY")

    # Gmail settings
    GMAIL_API_CREDENTIALS: Optional[str] = os.getenv("GMAIL_API_CREDENTIALS")

    # Google Workspace settings
    GOOGLE_SERVICE_ACCOUNT_PATH: Optional[str] = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH")
    GOOGLE_WORKSPACE_DOMAIN: Optional[str] = os.getenv("GOOGLE_WORKSPACE_DOMAIN")

    # Email tracking settings
    TRACKING_BASE_URL: str = os.getenv("TRACKING_BASE_URL", "http://localhost:8003")

    # Temporal settings
    TEMPORAL_HOST: Optional[str] = os.getenv("TEMPORAL_HOST")
    TEMPORAL_NAMESPACE: Optional[str] = os.getenv("TEMPORAL_NAMESPACE")
    TEMPORAL_API_KEY: Optional[str] = os.getenv("TEMPORAL_API_KEY")
    # APP_ENV is read via temporal_workflows.topology.app_env(), which
    # normalizes aliases (prod → main, staging → dev) and falls back to
    # PRELUDE_ENV/ENVIRONMENT. A duplicate raw field here would silently
    # diverge under aliased values, so it is intentionally not exposed.
    TEMPORAL_QUEUE_PREFIX: Optional[str] = os.getenv("TEMPORAL_QUEUE_PREFIX")
    TEMPORAL_WORKFLOW_ID_PREFIX: Optional[str] = os.getenv("TEMPORAL_WORKFLOW_ID_PREFIX")
    TEMPORAL_LOCAL_WORKER_ID: Optional[str] = os.getenv("TEMPORAL_LOCAL_WORKER_ID")
    SCHEDULER_TASK_QUEUE: Optional[str] = os.getenv("SCHEDULER_TASK_QUEUE")
    MASS_EMAIL_TASK_QUEUE: Optional[str] = os.getenv("MASS_EMAIL_TASK_QUEUE")
    SUMMARY_SCHEDULE_ID: Optional[str] = os.getenv("SUMMARY_SCHEDULE_ID")
    SIGNAL_SCHEDULE_ID: Optional[str] = os.getenv("SIGNAL_SCHEDULE_ID")
    TEMPORAL_SCHEDULER_OWNER: bool = os.getenv("TEMPORAL_SCHEDULER_OWNER", "").lower() in ("1", "true", "yes", "on")
    ENABLE_TEMPORAL_SCHEDULER_WORKER: bool = os.getenv("ENABLE_TEMPORAL_SCHEDULER_WORKER", "").lower() in ("1", "true", "yes", "on")
    ENABLE_TEMPORAL_MASS_EMAIL_WORKER: bool = os.getenv("ENABLE_TEMPORAL_MASS_EMAIL_WORKER", "").lower() in ("1", "true", "yes", "on")
    ALLOW_LOCAL_TEMPORAL_EMAIL_WORKER: bool = os.getenv("ALLOW_LOCAL_TEMPORAL_EMAIL_WORKER", "").lower() in ("1", "true", "yes", "on")
    # Legacy all-worker flag retained for migration/rollback. Prefer
    # ENABLE_TEMPORAL_SCHEDULER_WORKER and ENABLE_TEMPORAL_MASS_EMAIL_WORKER.
    ENABLE_TEMPORAL_WORKER: bool = False
    SHOW_EMAIL_SYNC_LOGS: bool = os.getenv("SHOW_EMAIL_SYNC_LOGS", "false").lower() == "true"

    # Management Database settings (for multi-tenant discovery)
    MANAGEMENT_DB_HOST: Optional[str] = None
    MANAGEMENT_DB_PORT: Optional[int] = None
    MANAGEMENT_DB_NAME: Optional[str] = None
    MANAGEMENT_DB_USER: Optional[str] = None
    MANAGEMENT_DB_PASSWORD: Optional[str] = None

    # CORS settings
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = os.getenv("CORS_ALLOW_METHODS", "*")
    CORS_ALLOW_HEADERS: str = os.getenv("CORS_ALLOW_HEADERS", "*")

    @property
    def cors_origins_list(self) -> list:
        """Parse CORS origins string into list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def cors_allow_methods_list(self) -> list:
        """Parse CORS methods string into list."""
        if self.CORS_ALLOW_METHODS == "*":
            return ["*"]
        return [m.strip() for m in self.CORS_ALLOW_METHODS.split(",")]

    @property
    def cors_allow_headers_list(self) -> list:
        """Parse CORS headers string into list."""
        if self.CORS_ALLOW_HEADERS == "*":
            return ["*"]
        return [h.strip() for h in self.CORS_ALLOW_HEADERS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()
