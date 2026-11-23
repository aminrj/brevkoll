# 0002. Send a Content-Security-Policy header on every response

Status: accepted (the pull request that carried it was merged by the owner)
Issue: #15   Date: 2026-11-21

## Context
"Same-origin only" is enforced today only by reading the templates. Nothing in the browser stops a later regression from
loading a font, script or image from a third party, which would leak the visitor's IP. Adding the header touches `main.py`,
which the spec's "UI only" scope does not list.

## Decision
One HTTP middleware in `main.py` adds `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self';
img-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'` to every
response. No `unsafe-inline`, no `unsafe-eval`. The htmx config meta sets `includeIndicatorStyles:false` so htmx injects no
inline `<style>`; the indicator rules live in `style.css`. Templates carry no `style=` attribute.

## Consequences
A template that loads anything off-origin breaks visibly in the browser, not only in a test. Inline styles and scripts are
off the table. If the staged build shows the `data:` calendar download or htmx blocked, the policy is wrong and must be
fixed here, not loosened with `unsafe-inline`. If the human declines, phase 3 is dropped and the template and stylesheet
tests remain the only enforcement.
