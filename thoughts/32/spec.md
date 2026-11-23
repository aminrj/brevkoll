# Spec: #32 Show the app version on /healthz and in the page footer

Status: approved

**Real user:** the owner (deploying staged builds)   **Size:** S   **Timebox:** 1 h   **Kill date:** 2026-11-29

## Problem

When testing staged builds on a phone, the owner cannot tell which build is running. On 2026-11-22 they tested an old build without knowing it.

## What v1 does (one sentence)

`GET /healthz` returns the app version alongside its status, and both the index and result pages show the version in a small muted footer.

## User flow
1. The owner opens the phone browser on the staged build.
2. They glance at the bottom of the page and see `brevkoll 0.1.0` (or whatever version is installed).
3. If needed, they check `GET /healthz` in a terminal and see `{"status": "ok", "version": "0.1.0"}`.

## Acceptance criteria (each one becomes a holdout test)
- [ ] AC1: Given a GET to `/healthz`, when the response is parsed as JSON, then it contains `"status": "ok"` and a `"version"` key whose value is a non-empty string.
- [ ] AC2: Given a GET to `/`, when the HTML response is returned, then the body contains the version string inside a `<footer>` element.
- [ ] AC3: Given the package metadata is available, when the version is read, then it comes from `importlib.metadata.version("app")`; when the package is not installed (metadata unavailable), then the string `"unknown"` is used instead.

## Contract (agents must respect this exactly; holdout tests depend on it)
- `GET /healthz` returns `{"status": "ok", "version": "<string>"}` with HTTP 200. The `"version"` value is a non-empty string.
- The version string is read via `importlib.metadata.version("app")` and falls back to `"unknown"` when the metadata is not available.
- Both `GET /` (index) and `POST /ui/decode` result pages include a `<footer>` element containing the version string (e.g. `brevkoll 0.1.0`).

## Out of scope
- Changing the Dockerfile or CI to bake in a version.
- Adding a new dependency.
- Versioning the API separately from the package.

## Assumptions

- The package name in `pyproject.toml` is `"app"` (matching `importlib.metadata.version("app")`).
- The version string is the package version from `pyproject.toml` (`0.1.0`).
- The footer can be a single `<footer class="footer">` element placed at the bottom of `<main>` in both `index.html` and `result.html`.

## Sketch

Add a small helper in `app/ui.py` (or `app/routes.py`) that reads the version with a `try/except` around `importlib.metadata.version("app")`. Pass it to the template context. Add a `<footer>` to both `index.html` and `result.html`.
