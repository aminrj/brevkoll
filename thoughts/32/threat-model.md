# Threat model: #32 Show the app version on /healthz and in the page footer

## Assets

The package version string from `pyproject.toml` via `importlib.metadata.version("app")`. This is non-sensitive metadata already visible through `pip show app`.

## Entry points and trust boundaries

| Entry point | Trust boundary | Notes |
|---|---|---|
| `GET /healthz` | Public, unauthenticated | Returns JSON with status + version |
| `GET /` (index page) | Public, unauthenticated | Serves HTML with a new footer |
| `POST /ui/decode` (result page) | Public, unauthenticated | Serves HTML with a new footer |

No new external dependencies, no new secrets, no new network calls.

## Data flow to models

| Data | Model (local / cloud) | Why acceptable |
|---|---|---|
| _(no change to model interaction)_ | | |

This change does not modify any LLM call, prompt, or output handling.

## Threats and controls

| Category | Threat in this app | Control (in code) | Enforcing test | Decision |
|---|---|---|---|---|
| LLM01 Prompt injection | Not applicable — no model interaction changes. | N/A | N/A | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM02 Sensitive information disclosure | The version string is public but non-sensitive; it is already available via `pip show`. | Version is read from package metadata only; no secrets or PII are included. | Holdout test checks `/healthz` returns a version string but no other fields. | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM05 Improper output handling | Not applicable — no model output is handled. | N/A | N/A | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM06 Excessive agency | Not applicable — no tool use or actions added. | N/A | N/A | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM07 System prompt leakage | Not applicable — no system prompt changes. | N/A | N/A | ACCEPTED (provisional, shown at Checkpoint 3) |
| LLM10 Unbounded consumption | Not applicable — no model calls added. | N/A | N/A | ACCEPTED (provisional, shown at Checkpoint 3) |
| Web: authn/z, IDOR, CSRF, SSRF, upload handling | Version disclosure via `/healthz` or footer could help an attacker identify known CVEs for this version. | Minimal attack surface: one extra JSON field and one HTML fragment. No auth, IDOR, or SSRF vectors introduced. | Holdout tests verify `/healthz` response shape and footer presence. | ACCEPTED — the owner intentionally wants this visible to distinguish staged builds. |

## Accepted risks

| Risk | Rationale |
|---|---|
| An attacker learns the deployed version and targets known vulnerabilities | The owner's stated goal is to distinguish staged builds on a phone; the version must be visible. The app has no database and no authenticated endpoints, so the attack surface from version knowledge is minimal. |
