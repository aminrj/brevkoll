# Spec: #36 Strip markdown code fences from model responses before parsing

Status: approved

**Real user:** a parent who uploads a Swedish letter PDF   **Size:** S   **Timebox:** 1 h   **Kill date:** 2026-11-30

## Problem

The model returns the JSON response wrapped in Markdown code fences (````json … ````). The `parse_model_output` function calls `ModelOutput.model_validate_json(raw)` on the raw string, which fails because of the fence markers, raising `BadModelOutput` with the message "The model returned an unusable answer." — even though the model produced a perfectly valid JSON payload.

## What v1 does (one sentence)

`parse_model_output` strips optional leading/trailing Markdown code fences (with an optional `json` language tag) from the model response before passing it to `model_validate_json`.

## User flow
1. The parent uploads a Swedish letter PDF.
2. The model returns a JSON response wrapped in ````json … ````.
3. The app strips the fences, parses the JSON, and shows the decoded letter — not an error.

## Acceptance criteria (each one becomes a holdout test)
- [ ] AC1: Given a model response wrapped in ````json … ```` fences, when `parse_model_output` is called, then the JSON inside is parsed successfully and `BadModelOutput` is not raised.
- [ ] AC2: Given a model response wrapped in ```` … ```` fences (no language tag), when `parse_model_output` is called, then the JSON inside is parsed successfully.
- [ ] AC3: Given a plain JSON response with no fences, when `parse_model_output` is called, then it behaves exactly as before (backward compatible).
- [ ] AC4: Given a response where the fences are present but the JSON inside is invalid, when `parse_model_output` is called, then `BadModelOutput` is raised.

## Contract (agents must respect this exactly; holdout tests depend on it)
- `parse_model_output(raw: str) -> ModelOutput` — the function signature is unchanged.
- Markdown code fences are detected by the pattern: an optional line starting with ````json` or `````, followed by content, followed by `````.
- The function strips the fences and then calls `ModelOutput.model_validate_json` on the trimmed inner content.
- If the inner content is not valid `ModelOutput` JSON, `BadModelOutput` is still raised.
- All other behaviors (extra field rejection, length limits, missing fields) remain identical.

## Out of scope
- Changing the model prompt to stop producing code fences.
- Handling other non-JSON wrapping formats (XML, HTML, etc.).
- Adding a config flag to enable/disable fence stripping.

## Assumptions
- The model consistently uses standard Markdown code fences (three backticks) with an optional `json` language identifier.
- The fences, if present, wrap the entire response with no leading/trailing content outside them.
- The inner JSON is always a single object (never an array or primitive).

## Sketch

Add a `_strip_markdown_fence` helper in `app/llm.py` that uses a simple regex to strip leading ````json`/```` and trailing ``````, then calls `model_validate_json` on the result. Update `parse_model_output` to use it.
