import secrets
import hmac


def generate_token() -> str:
    """Generate a cryptographically secure URL-safe token for session auth."""
    return secrets.token_urlsafe(32)


def validate_token(provided: str, expected: str) -> bool:
    """Validate a token using constant-time comparison to prevent timing attacks."""
    return hmac.compare_digest(provided, expected)
