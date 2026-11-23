# Spec: #6 Warn about OCR character errors on the result page

Status: approved

**Real user:** a parent reading a school letter on their phone   **Size:** S   **Timebox:** 1 h   **Kill date:** 2026-11-29

## Problem

Tesseract misreads characters — for example, `@` as `Q` — so email addresses and other special characters in the action items are wrong. The existing "Machine generated" notice is too generic; the parent does not know to check individual characters.

## What v1 does (one sentence)

Add a second, specific notice on the result page that tells the user to check email addresses and phone numbers because OCR may have misread characters.

## User flow
1. The parent uploads a letter and sees the result.
2. They read the first notice ("Machine generated…") and below it a second notice that mentions email addresses and phone numbers may contain OCR errors.
3. They spot the wrong email, open the original photo, and correct it.

## Acceptance criteria (each one becomes a holdout test)
- [ ] AC1: Given any decoded letter, when the result page HTML is returned, then it contains a notice element whose text mentions email addresses and OCR errors.
- [ ] AC2: Given a GET to `/api/decode`, when the JSON response is parsed, then it does not contain an `ocr_warning` field (the API contract is unchanged).
- [ ] AC3: Given the result page HTML, then the new notice appears before the "What to do" heading.

## Contract (agents must respect this exactly; holdout tests depend on it)
- **Result page:** `<p class="notice">` or `<p class="note">` containing text that mentions "email" and "OCR" (case-insensitive), placed after the existing "Machine generated" notice and before the first `<h2>` on the result page.
- **API contract unchanged:** `POST /api/decode` still returns `{"summary": str, "actions": [str], "dates": [{"date": "YYYY-MM-DD", "description": str}], "ics": str}` — no new fields.
- **CSS:** the new notice reuses existing `.notice` or `.note` styles (no new class required).

## Out of scope
- Improving OCR accuracy (Tesseract settings, image preprocessing).
- Extracting or validating email addresses from OCR text.
- Changing the API response shape.
- Adding the warning to the index page or error pages.

## Assumptions
- The existing `.notice` class styling is sufficient; no new CSS is needed.
- The notice text can be a short sentence: "Email addresses, phone numbers and special characters may contain OCR errors — check the original letter."
