"""Email open tracking service."""

import secrets
import base64
from datetime import datetime, timedelta, timezone


class TrackingService:
    """Service for email open tracking via invisible pixel."""

    def __init__(self, base_url: str):
        """Initialize tracking service with base URL."""
        self.base_url = base_url.rstrip('/')

    def generate_tracking_token(self) -> str:
        """Generate cryptographically secure tracking token."""
        return secrets.token_urlsafe(32)

    def get_token_expiration(self) -> datetime:
        """Get token expiration timestamp (30 days from now)."""
        return datetime.now(timezone.utc) + timedelta(days=30)

    def _encode_email(self, email: str) -> str:
        """Encode email address for URL."""
        return base64.urlsafe_b64encode(email.encode()).decode()

    def add_tracking_pixel(self, html_content: str, tracking_token: str, user_email: str = None) -> str:
        """Inject invisible 1x1 tracking pixel into HTML email.

        Args:
            html_content: HTML email body
            tracking_token: Unique tracking token
            user_email: User email for database routing (required for multi-tenant)
        """
        pixel_url = f"{self.base_url}/t/o.gif?t={tracking_token}"
        if user_email:
            encoded_email = self._encode_email(user_email)
            pixel_url += f"&e={encoded_email}"

        pixel_html = f'<img src="{pixel_url}" width="1" height="1" style="display:none;" alt="" />'

        if '</body>' in html_content:
            return html_content.replace('</body>', f'{pixel_html}\n</body>')
        return html_content + pixel_html
