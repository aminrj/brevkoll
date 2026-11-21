# 0001. The weekday is computed in the UI layer, not in DecodeResult

Status: proposed
Issue: #15   Date: 2026-11-21

## Context
The spec wants a weekday beside each date. Nothing computes one today. `DecodeResult` is also the JSON response of
`POST /api/decode`, so a new field there changes a public contract the spec puts out of scope. The system locale is not
reliable for day names, and the answer language can be en, sv, ar or uk.

## Decision
`app.ui` builds a view model (`DateView`) from each `DateItem`: the weekday comes from `datetime.date.fromisoformat(...).weekday()`
and a fixed name table per supported language in code. `DecodeResult`, `DateItem` and the API response do not change.
The weekday is shown in the answer language; an unknown language falls back to English.

## Consequences
The API stays byte-identical. The weekday exists only in the HTML. Adding a language means adding a row to the name table
(a test fails if a supported language has no row). Do not move the weekday into `DecodeResult` without a new decision.
