"""SSRF guard — assert_safe_url blocks metadata/loopback/private/non-http targets."""
import pytest

from modules.common.ssrf import assert_safe_url


@pytest.mark.no_db
@pytest.mark.parametrize("bad", [
    "http://169.254.169.254/latest/meta-data/iam/security-credentials/",  # cloud metadata
    "http://127.0.0.1/admin",
    "http://localhost:5678/",
    "file:///etc/passwd",
    "gopher://x/",
    "http://0.0.0.0/",
])
def test_assert_safe_url_rejects(bad):
    with pytest.raises(ValueError):
        assert_safe_url(bad)


@pytest.mark.no_db
def test_assert_safe_url_allows_public():
    # Public host must not raise (resolves to a public IP).
    assert_safe_url("https://www.example.com/image.jpg")


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_process_image_blocks_private_url():
    from modules.ops_push.image_pipeline import process_image
    with pytest.raises(ValueError):
        await process_image("http://169.254.169.254/latest/meta-data/")
