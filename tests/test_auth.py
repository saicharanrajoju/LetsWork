from letswork.auth import generate_token, validate_token


def test_generate_token_length():
    """Token should be at least 32 characters."""
    token = generate_token()
    assert len(token) >= 32


def test_validate_token_correct():
    """Matching tokens should return True."""
    token = generate_token()
    assert validate_token(token, token) is True


def test_validate_token_incorrect():
    """Non-matching tokens should return False."""
    token = generate_token()
    assert validate_token("wrong-token", token) is False
