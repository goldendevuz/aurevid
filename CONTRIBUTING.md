# Contributing to Aurevid

Thanks for helping! A few rules keep the project original, legal and safe.

## Ground rules

1. **Original work only.** Do not copy code, text, preset names, prompts, designs, logos or assets
   from other products. Studying permissively licensed open-source projects for architecture ideas
   is fine; copying their code requires a compatible licence and attribution in
   `THIRD_PARTY_LICENSES.md`. Never take code from repositories without a LICENSE file.
2. **Permissive dependencies only** (MIT, BSD, Apache-2.0, ISC, ...). Run `scripts/licenses.sh` and
   commit the updated `THIRD_PARTY_LICENSES.md`. Ask in the PR before adding anything copyleft.
3. **New models/providers:** record licence and terms in `MODEL_LICENSES.md` first. Unclear or restricted → not offered (enforced in code, see MODEL_LICENSES.md, rule 3).
4. **No secrets in git.** Install hooks: `pip install pre-commit && pre-commit install` (runs gitleaks).
5. **SPDX header** on every source file: `SPDX-License-Identifier: AGPL-3.0-or-later`.

## Workflow

- Branch from `main`, keep PRs small and focused, one vertical slice at a time.
- Backend: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`
- Frontend: `npm run typecheck && npm test && npm run build`
- Schema change: `uv run alembic revision --autogenerate -m "..."`, review the file, commit it.
- Every new endpoint needs an owner check and an IDOR test (see `tests/test_idor.py`).
- All UI strings go through i18n; add keys to `en.json`, `uz.json` and `ru.json` (a test enforces parity).

## Licence of contributions

By contributing you agree your contribution is licensed under AGPL-3.0-or-later.
Security issues: see [SECURITY.md](SECURITY.md), not public issues.
