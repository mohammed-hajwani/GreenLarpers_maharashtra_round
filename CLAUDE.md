# Re:Learn — Claude Code Operating Rules

Read PRD.md fully before writing any code. PRD.md is the source of truth for scope, schemas, interfaces, and acceptance gates.

## Hard rules
- No comments of any kind in any file: no inline comments, docstrings, or block comments in Python, YAML, Makefile, shell, or config files.
- Work stage by stage in the order defined in PRD.md section 10. Do not start a stage until the previous gate command passes.
- Before each stage, write a short plan (files to create, functions, tests) and then implement it.
- After each stage: run its gate command, fix failures, then commit with message `stage N: <name>`.
- The system must run fully offline by default using StubLLMClient. Never require an API key for tests or gates.
- All randomness is seeded from configs/default.yaml (`seed: 42`).
- Public functions are fully type-annotated. Data crossing module boundaries uses the pydantic models in `src/relearn/schemas.py`. Do not change those models without updating PRD.md section 6.
- The main model trains on a Colab T4 in under 20 minutes. Local CPU runs are smoke tests only. Prefer smaller models over longer training.
- The deliverable is a publicly hosted demo on Hugging Face Spaces using free CPU only. The entrypoint is `app.py`. Nothing at runtime may require a GPU, local files outside the repo, or an API key.
- Notebooks in `notebooks/` contain code cells only: no markdown cells and no comments.
- Never commit tokens or secrets. Read them from environment variables and document them in `.env.example`.
- At stages marked HUMAN in PRD.md section 10, finish the preparation, print the matching steps from PRD.md section 16 with real values filled in, and stop until the user confirms.
- Ask the user a question only if blocked; otherwise choose the default stated in PRD.md and note the choice in `DECISIONS.md`.

## Commands
- `make setup` install dependencies
- `make data` generate dataset
- `make train` train baseline and main model
- `make eval` run full evaluation and write `reports/metrics.json`
- `make test` run pytest
- `make gate STAGE=<n>` run the gate for a stage
- `make app` launch Streamlit UI for development
- `make deploy-dry` list the files that would be uploaded to the Space
- `make smoke URL=<space_url>` run the remote smoke test

## Style
- Python 3.11, ruff formatting, pytest for tests.
- Small modules with single responsibility; no module over 300 lines.
- Configuration lives in `configs/`; no magic numbers in code.
