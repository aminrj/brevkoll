# <app name>

<One or two sentences: what it does and who it is for (the named user from spec.md).>

## What it does

<The v1 behaviour in plain words, with the endpoints or pages.>

## Run it

    uv sync
    uv run fastapi dev src/app/main.py

Container: <image build and run command, including read-only flags and the model settings>.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `<NAME>` | `<default>` | <one line> |

## Limits and what is not done

<Size, rate and budget limits. Known gaps. Anything the next person must not assume.>

## How it was built

Specs, threat model, plan and validation report for each issue are in `thoughts/<issue>/`. Decisions are in `docs/decisions/`.
