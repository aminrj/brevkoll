# Spec: #29 Accept 256 KB PDFs without "File too large"

Status: approved

**Real user:** a parent who uploads a scanned school letter (PDF)   **Size:** S   **Timebox:** 1 h   **Kill date:** 2026-11-29

## Problem

A user uploaded a 256 KB PDF and received "File too large." The app's `MAX_BYTES` is 10 MB, so a 256 KB file should be accepted. The error suggests an internal size limit is triggering before the app's own check.

## What v1 does (one sentence)

Ensure files up to 10 MB are accepted through the full upload pipeline without hitting an internal size limit.

## User flow
1. The parent opens brevkoll on their phone.
2. They take a photo of a school letter and save it as a PDF (~256 KB).
3. They upload it and get the decoded result, not an error.

## Acceptance criteria (each one becomes a holdout test)
- [ ] AC1: Given a 256 KB PDF uploaded to `/api/decode`, when the request completes, then the response is 200 (not 413 or 500).
- [ ] AC2: Given a file just under 10 MB uploaded to `/api/decode`, when the request completes, then the response is 200.
- [ ] AC3: Given a file 1 byte over 10 MB uploaded to `/api/decode`, when the request completes, then the response is 413 with `{"error": "File too large."}`.

## Contract (agents must respect this exactly; holdout tests depend on it)
- `app.upload.MAX_BYTES = 10 * 1024 * 1024` (10 MB) — the hard upper bound on uploaded file size.
- `app.upload.read_limited(file, max_bytes=MAX_BYTES)` reads the file in 64 KB chunks and raises `app.errors.TooLarge` when the total exceeds `max_bytes`.
- `app.errors.TooLarge` → HTTP 413, body `{"error": "File too large."}` (JSON) or the equivalent HTML error page.
- Both `/api/decode` and `/ui/decode` accept `file: UploadFile` and `language: str` and return the decoded result.

## Out of scope

- Increasing the limit beyond 10 MB.
- Streaming the file to disk instead of memory (the app is single-user on a private cluster).
- Adding progress indicators or chunked upload support.

## Assumptions

- The root cause is FastAPI's default `UploadFile.max_file_size` (1 MB) or an overly strict middleware check, not the 10 MB `MAX_BYTES`.
- The 256 KB file is a valid PNG, JPEG, or PDF (content-type validated by `sniff_kind`).

## Sketch

Set `max_file_size=MAX_BYTES` on the `File()` parameters in `routes.py` so FastAPI's internal limit matches the app's limit. Verify the middleware's `content-length` check does not reject files under 10 MB.
