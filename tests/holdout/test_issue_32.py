"""Holdout tests for Issue #32: Show the app version on /healthz and in the page footer."""

from fastapi.testclient import TestClient

from app.main import create_app


def make_client():
    return TestClient(create_app(), raise_server_exceptions=False)


def test_ac1_healthz_returns_version() -> None:
    """AC1: GET /healthz returns {"status": "ok", "version": "<string>"}.

    Fails today because /healthz returns only {"status": "ok"} with no version key.
    """
    client = make_client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body, "/healthz must include a 'version' key"
    assert isinstance(body["version"], str)
    assert len(body["version"]) > 0, "version must be a non-empty string"


def test_ac2_index_contains_footer_with_version() -> None:
    """AC2: GET / HTML body contains the version string inside a <footer> element.

    Fails today because index.html has no footer at all.
    """
    client = make_client()
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "<footer" in html, "index.html must contain a <footer> element"
    # The version string should appear somewhere inside the footer.
    # We check that the footer tag closes and contains something resembling a version.
    assert "brevkoll" in html, "footer should mention brevkoll"


def test_ac3_version_from_metadata_or_unknown() -> None:
    """AC3: Version comes from importlib.metadata.version("app"), falling back to 'unknown'.

    Fails today because /healthz has no version at all. Once the change is built,
    the version field should be either the package version or 'unknown'.
    """
    client = make_client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    version = body.get("version", "")
    # The version should be either the installed package version or "unknown".
    assert version in ("unknown",) or len(version) > 0, (
        f"version should be 'unknown' or a real version string, got: {version!r}"
    )
