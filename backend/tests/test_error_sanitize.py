"""sanitize_error redacts credential-shaped substrings and truncates."""
import pytest

from modules.common.sanitize import sanitize_error


@pytest.mark.no_db
def test_redacts_bearer_and_secret():
    s = sanitize_error("auth failed: Bearer abc123tok client_secret=shh password=hunter2")
    assert "abc123tok" not in s
    assert "shh" not in s
    assert "hunter2" not in s
    assert "[REDACTED]" in s


@pytest.mark.no_db
def test_truncates():
    assert len(sanitize_error("x" * 5000)) <= 300
