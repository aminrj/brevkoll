# Threat model: #15

Status: DRAFT. Every decision is ACCEPTED; the human decides.

Scope: a restyle of `index.html`, `result.html`, `error.html` and `style.css`. The spec says nothing the app computes changes: no new endpoint, no new input, no change to OCR, the prompt, the model call, redaction, dates or the `.ics`. The threats below are the ones a UI change can introduce or weaken. The controls of `thoughts/1/threat-model.md` stay in force and are not repeated.

## Assets

- Letter content shown in the result (summary, actions, dates, quoted wording). It reaches the browser only; nothing is stored.
- The reader's trust in the deadline: a layout that hides or misorders the dates, or makes the machine-generated notice look like a verified fact, leads to a missed deadline.
- The "nothing is stored, nothing leaves except to the model" promise: an external request from the page would leak the visitor's IP and the fact that they use the app.
- Model-derived text is untrusted. Templates are where it meets the DOM.

## Entry points and trust boundaries

1. Templates rendering model-derived strings (`result.summary`, `result.actions`, `item.description`) and letter-derived strings (`item.date`). Untrusted.
2. `data:text/calendar` link built from `result.ics` with `urlencode`. The content is code-built, but it contains escaped model text.
3. Static files under `/static` (the stylesheet, the vendored `htmx.min.js`). Trusted, served same-origin.
4. Browser loading the page: any new `<link>`, `<script>`, `@import`, `url()` or `@font-face` is a new outbound request.
5. The wait indicator and the disabled button: client-side state during a request.
6. The error template: shows fixed messages, uses `role="alert"`.

## Data flow to models

| Data | Model (local / cloud) | Why acceptable |
|---|---|---|
| None changed (ACCEPTED) | Unchanged from #1 | This issue touches presentation only. No prompt, schema or model setting changes. A test that the prompt builder and model client are untouched is not needed; the diff guard in review covers it. |

## Threats and controls

| Category | Threat in this app | Control (in code) | Enforcing test | Decision |
|---|---|---|---|---|
| LLM01 Prompt injection | A new layout that reorders or emphasises text could make injected summary text look like authoritative instructions, for example a styled "deadline" line the model wrote. | Only code-parsed dates get the large date treatment. Summary and actions keep plain styling. The machine-generated notice stays visible in the result (quiet, not hidden or `display:none`). No prompt change. | Holdout AC7 (notice, summary, actions and dates all present). Unit: render the result with a summary claiming "deadline cancelled" and check the large-date markup holds only `result.dates` items. | ACCEPTED |
| LLM02 Sensitive information disclosure | The restyle adds an external font, image, analytics or CDN request, so the visitor's IP and use of a school-letter tool leaks to a third party. Letter text must also stay out of URLs. | Same-origin only: system font stack, no `@font-face`, no `@import`, no external `url()`, no external `<link>`/`<script>`/`<img>`. No `hx-get` or link that puts letter text in a query string. | Holdout AC1 and AC4 (no external resources, no font-face or import). Unit: scan the stylesheet and rendered pages for `http://`, `https://` and `//` URLs (only same-origin paths such as `/static/...` and the `data:text/calendar` link are allowed). | ACCEPTED |
| LLM05 Improper output handling | Restyling the result tempts the implementer to use `\|safe`, `innerHTML` or markup built by string concatenation (for example to bold part of an action or build the quotation). Model text then runs as HTML. | Keep Jinja autoescape for every model or letter string. No `\|safe`, no `Markup()`, no new JavaScript. The date, weekday and wording are separate escaped fields; the weekday is computed in code from the ISO date, not taken from the model. | Unit (carries over from #1, run on the new template): a summary, action and date description containing `<script>` and `"><img onerror=...>` are escaped in the rendered result. Unit: templates contain no `\|safe`. Holdout AC3 (only script is htmx, no inline script). | ACCEPTED |
| LLM05 (calendar link) | A restyle that changes how the `.ics` link is built (new button, new `data:` URL form) could break escaping and let model text inject a property or event. | The link and `result.ics` construction stay as they are; only classes change. The `.ics` is untouched, per out of scope. | Existing unit: an action with `\r\nBEGIN:VEVENT` creates no second VEVENT. Unit: the link `href` in the new result is still `data:text/calendar;charset=utf-8,` plus the urlencoded `ics`. | ACCEPTED |
| LLM05 (misread date) | "Dates" shown large with a weekday: a wrong weekday or a layout that drops the year would mislead. | Weekday computed by code from the ISO date (`datetime.date.weekday`), with the year always shown. Wording shown beside it as a quotation so the parent can check (R2 of #1). | Unit: table test of date to weekday, including a leap day and a year boundary. Unit: the rendered date item contains the full ISO date and the wording. | ACCEPTED |
| LLM06 Excessive agency | None added. The model still has no tools and the UI adds no action beyond the user's own `.ics` download. | No new JavaScript, no new `hx-*` attributes that send data anywhere. The form still posts only to `/ui/decode`. | Holdout AC3. Unit: the route allowlist test from #1 still passes (no new route). | ACCEPTED |
| LLM07 System prompt leakage | The wait text or error text could be changed to show more detail (for example a raw error). | Error template keeps fixed generic messages and `role="alert"`. No exception text in templates. | Holdout AC7 (`role="alert"` kept). Existing unit: error bodies do not contain the prompt. | ACCEPTED |
| LLM10 Unbounded consumption | Impatient users double-tap the button during the long model wait and submit the same letter twice, doubling OCR and model cost. The spec wants the button disabled while a request runs. | Disable the button during the request with htmx only: `hx-disabled-elt="this"` on the form button (an attribute, no new script). The rate limit and daily budget stay the real control, since a client can ignore the UI. The page HTML stays under 8 KB and the stylesheet under 12 KB so the static path stays cheap. | Unit: the rendered form has `hx-disabled-elt` pointing at the submit button and the wait element is not hidden by default for assistive tech. Holdout AC2 (size caps). Existing unit: rate limit and budget still enforced. | ACCEPTED |
| Web: authn/z, IDOR | None. No new routes or data. | No new route. | Existing route allowlist test. | ACCEPTED |
| Web: CSRF | None added. The form action and method are unchanged. No cookie. | No cookies, no CORS headers (unchanged). | Existing unit: no `Set-Cookie`, no `Access-Control-Allow-Origin`. | ACCEPTED |
| Web: SSRF | None. The UI adds no fetch of its own. | The app still fetches only the configured model endpoint. | Existing unit from #1. | ACCEPTED |
| Web: upload handling | The restyle of the file field could loosen `accept`, `required` or the limits text, or change the field name. Client checks are not controls, but a changed `name` breaks the endpoint. | Keep `name="file"`, `name="language"`, `accept`, `required` and the size text. Server checks stay the control. | Unit: the rendered form posts `file` and `language` to `/ui/decode` with multipart encoding. Holdout AC5 (every input and select has a label). | ACCEPTED |
| Web: content security | No Content-Security-Policy exists, so nothing in the browser enforces "same-origin only" if a template regresses. Inline `style=` attributes would also block a strict CSP later. | Propose a `Content-Security-Policy` response header on the HTML pages: `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`. The `data:` calendar link is a user-initiated download, not a subresource load, so it should not need a directive; verify on the staged build. Needs the human's decision because it touches `main.py` (behaviour outside the strict UI scope). The htmx config `<meta name="htmx-config">` is not a script and is allowed. htmx adds an inline indicator `<style>` unless `includeIndicatorStyles` is false, which would break `style-src 'self'`; set it false in that meta tag and style the indicator in `style.css`. | Unit: the index response carries the header, the policy has no `unsafe-inline` or `unsafe-eval`, and no template has an inline `style=` attribute or `<style>` block. Manual check on the staged build that the htmx request, the busy text and the `.ics` download still work under the policy. | ACCEPTED (see Q1) |

## Accepted risks

- **R1 (ACCEPTED):** the date weekday is derived from OCR text through code; an OCR error in the date still shows a wrong large date. Mitigation is unchanged from R2 of #1: the letter's own wording is shown beside it and the notice stays visible.
- **R2 (ACCEPTED):** disabling the button is a UI nicety, not a control. A script or a second tab can still send requests; the rate limit and the daily budget bound the cost.
- **R3 (ACCEPTED):** the dark-mode, contrast and tap-target criteria are checked partly by hand (AC8, the phone check). Automated tests cover only what is statically checkable (presence of the rules, size, no external requests).
- **R4 (ACCEPTED):** the `data:` calendar link may be blocked by some mobile browsers. This is existing behaviour and out of scope here.

## Open questions for the human

- Q1: Add the `Content-Security-Policy` header? It is the only control that enforces "same-origin only" at runtime, but it is a change to `main.py` and the htmx indicator style handling, which the spec lists as outside "UI only". If no, the same-origin rule is enforced only by tests of the templates and the stylesheet.
- Q2: Compute the weekday in code (small helper) or leave it out of the first slice? The spec asks for the weekday; showing it needs a few lines of Python, so "nothing the app computes changes" needs your reading.
- Q3: Which language is the weekday shown in: the answer language, or fixed? A name table in code is needed either way, since the system locale is not reliable.
