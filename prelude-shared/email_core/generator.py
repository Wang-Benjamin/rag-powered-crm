"""Re-export shim — generator now lives in email_core.generation.generator.
This file will be removed after all consumers update their imports (Phase 4e).
"""
from email_core.generation.generator import generate_email_with_ai

__all__ = ["generate_email_with_ai"]
