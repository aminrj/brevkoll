# factory-template

Template for apps built through my secure AI software factory. Each app starts here.

- `AGENTS.md`: rules for every coding agent (Claude Code reads it through `CLAUDE.md`).
- `thoughts/<issue>/`: the reviewable trail for each issue: spec, threat model, research, plan, validation.
- `.gitea/workflows/gates.yml`: lint, types, tests, security scans, holdout acceptance tests, and two guards
  (agents cannot touch holdout tests or workflows; new tests must fail on the old code). It runs on a self-hosted
  Gitea runner. The tools are pinned binaries with checksums; no Docker is used in CI.
- Agents run locally. `factory/scripts/dispatch.py <repo> <issue> <step>` runs one step in a git worktree of
  `agent/issue-<n>` and pushes only after the guards pass. There is no agent workflow in CI.
- Releases: the image is built on my machine, scanned with trivy, and pushed to the Gitea container registry.

## Running the container

The image sets `APP_ENV=prod` (the `fake` model provider is refused) and `APP_DATA_DIR=/data`. Configure the
local model with `LLM_PROVIDER=openai_compat`, `LLM_BASE_URL` and `LLM_MODEL`. Run it with a read-only root
filesystem; this is a run-time flag, not something the image can enforce:

    docker run --read-only --tmpfs /tmp -p 8000:8000 -e LLM_PROVIDER=openai_compat \
      -e LLM_BASE_URL=http://host:11434/v1 -e LLM_MODEL=<model> brevkoll

The web page is at `/`. It needs `src/app/static/htmx.min.js` (htmx 2.0.4, vendored).

Primary home is a private Gitea instance. This repository is a read-only public mirror.
