"""Acceptance tests for issue #32: show the app version on /healthz and in the page footer."""

from importlib import metadata
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_returns_version() -> None:
    """AC1: GET /healthz returns JSON with "status": "ok" and a non-empty "version" string."""
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["version"], str)
    assert len(body["version"]) > 0


def test_index_contains_version_footer() -> None:
    """AC2: GET / returns HTML with a <footer> element containing the version string."""
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "<footer" in html
    version_marker = "brevkoll "
    assert version_marker in html


def test_version_from_metadata_or_unknown() -> None:
    """AC3: when importlib.metadata.version("app") succeeds, returns that value;
    when it raises PackageNotFoundError, returns "unknown"."""
    from app.ui import get_version

    # When the package is installed, get_version returns the real version
    real_version = get_version()
    assert isinstance(real_version, str)
    assert len(real_version) > 0

    # When the package is not installed, get_version returns "unknown"
    with patch.object(metadata, "version", side_effect=metadata.PackageNotFoundError("app")):
        assert get_version() == "unknown"
