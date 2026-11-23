# Threat model: #<n>

## Assets

## Entry points and trust boundaries

## Data flow to models
| Data | Model (local / cloud) | Why acceptable |
|---|---|---|

## Threats and controls
| ID | Category | Threat in this app | Control (in code) | Enforcing test | Decision |
|---|---|---|---|---|---|
| T1 | LLM01 Prompt injection | | | | PROPOSED |
| T2 | LLM02 Sensitive information disclosure | | | | PROPOSED |
| T3 | LLM05 Improper output handling | | | | PROPOSED |
| T4 | LLM06 Excessive agency | | | | PROPOSED |
| T5 | LLM07 System prompt leakage | | | | PROPOSED |
| T6 | LLM10 Unbounded consumption | | | | PROPOSED |
| T7 | Web: authn/z, IDOR, CSRF, SSRF, upload handling | | | | PROPOSED |

Rows get IDs `T1`, `T2`, ... (add more as needed). A row decided `ACCEPTED` or `CHANGED: ...` needs a test
that carries `@pytest.mark.control("T<n>")` or a `# T<n>` comment; `scripts/trace.py` fails the build otherwise.
`REJECTED` rows need no test.

## Accepted risks
