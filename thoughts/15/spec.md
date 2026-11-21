# Spec: #15 UI refresh: a professional, fast interface for reading a letter on a phone

Status: approved

**Real user:** a parent of a school child who reads Swedish letters on a phone   **Size:** S   **Timebox:** 2 h   **Kill date:** 2026-12-05

## Problem

The page works but looks like an unstyled form. On a phone the result is hard to scan: the deadline and the things to do are not easy to find, the "machine generated" notice looks like an error, and nothing tells the parent what is happening during the wait for the model.

## What this does (one sentence)

Restyles the page and the result so a parent finds what to do and by when within a few seconds on a phone, without changing anything the app computes.

## Design direction (guardrails, not a mockup)

- **Look:** calm, editorial, utility. A warm off-white paper background and near-black ink, one accent colour used for the primary button, links and focus rings. Dark mode follows the system setting.
- **Not:** gradients, glass blur, glowing shadows, emoji or icon fonts, purple-blue palettes, hero banners, stacks of identical rounded cards, decorative animation. If it looks like a generic AI landing page, it is wrong.
- **Type:** the system font stack only, a clear scale (title, section heading, body, note), body text at least 17 px on a phone, tabular figures for dates.
- **Layout:** one column, about 40 rem wide, touch targets at least 44 px, the file field and the button full width on a phone. Result sections are separated by hairline rules, not boxes.
- **Result:** "What to do" first, as a list that is easy to check off by eye. "Dates" as a list with the date large and the weekday, the letter's own wording below it as a quotation. The machine-generated notice stays visible but quiet, not an alert. Errors keep `role="alert"`.
- **Speed:** no web fonts, no new JavaScript beyond the bundled htmx, no external requests, stylesheet under 12 KB, page HTML under 8 KB. The button is disabled while a request runs and the wait text shows at once.
- **Access:** every field has a label, focus is visible, contrast meets WCAG AA, reduced motion is respected.

## User flow

1. Open the page on a phone, take or pick a photo of the letter, choose the language.
2. Tap the button. It disables and a short wait message shows.
3. Read "What to do", then "Dates", then the summary. Tap the calendar link to add the dates.

## Acceptance criteria (each becomes a holdout test, except the last)

1. The page and the result load only same-origin resources: no external stylesheet, script, font or image.
2. All stylesheets together are at most 12 KB and the index page HTML is at most 8 KB.
3. The only script is the bundled htmx file. No inline script, no other file.
4. The stylesheet has no gradient, no backdrop filter, no blur, no font-face and no import. The templates contain no emoji.
5. The page has a language attribute, a viewport meta tag and a title. Every input and select has a label that points at it.
6. The stylesheet has a dark colour scheme rule, a reduced motion rule and a visible focus rule.
7. The result still shows the machine-generated notice, the summary, the actions, the dates with the calendar download, and "What to do" comes before "Dates". An error is still announced with `role="alert"`.
8. Phone check on the staged build (not a test): the owner finds the deadline in five seconds and says the look is professional, not generic.

## Out of scope

Behaviour, endpoints, OCR, the model, redaction, languages, the calendar file, new pages, a logo, a settings screen.

## Sketch

None. The implementer proposes the palette and type scale in the plan; the owner approves it there.
