# AGENTS.md

## Project boundary

`laoliuliu` is a private Web application for 2026 Macau draw data. It has five
approved product capabilities only:

1. administrator and child-user login/authorization;
2. 2026 issue 048 onward draw collection from the approved 00853 endpoints;
3. deterministic next-draw regular-zodiac transition frequency ranking;
4. OpenAI-compatible explanation of that fixed ranking;
5. deterministic top-ten number comparison and ten 3-of-3 reference groups.

Do not add Windows-client code, License/device binding, other number prediction
or scoring methods, other combination generation, exports, payment, or additional
data sources without explicit user approval.

## Analysis rule

- Use only 2026 issue 048 onward records.
- Read the latest special number and map it with that draw's source-provided
  zodiac anchor.
- Find earlier 2026 issue 048 onward draws with the same special-number zodiac.
- Include only matches that have an immediately following draw by open time.
- Count all six regular-zodiac occurrences in each following draw. Duplicate
  zodiacs in one draw count multiple times.
- Sort by occurrence count descending, then canonical zodiac order for ties.
- The first release outputs six zodiacs, not six numbers.
- AI may explain the deterministic result but may not change it.

Never describe empirical history frequency as guaranteed prediction accuracy.

## Number combination rule

- Start from the number occurrences inside the complete zodiac ranking's first
  six zodiacs for the latest issue.
- Count only the six regular numbers in each of the 20 draws immediately before
  the latest issue; exclude the latest issue and every special number.
- Keep numbers present in both sets. Rank by historical occurrences plus recent
  occurrences descending, then historical occurrences descending, recent
  occurrences descending, and number ascending. Keep ten numbers.
- Generate all unique three-number groups from those ten. Rank by summed score,
  summed historical occurrences, summed recent occurrences, then ascending number
  tuple. Return ten groups.
- These are historical reference groups, not guaranteed 3-of-3 predictions.

## Engineering rules

- Python 3.11+, type annotations, Black, Ruff, strict MyPy, Pytest.
- FastAPI, SQLAlchemy, Alembic, PostgreSQL, build-free same-origin HTML/CSS/JS.
- All secrets come from environment variables or ignored credential files.
- Never log passwords, session tokens, CSRF tokens, API keys, or connection URLs.
- Every network call uses explicit timeouts, bounded response sizes, and finite
  retries.
- Source snapshots and normalized draw records are stored separately.
- Draw writes are idempotent; conflicting issue contents fail closed.
- Browser sessions are opaque, HttpOnly, server-side records. State-changing
  calls require CSRF verification.
- API keys remain server-side and are encrypted at rest.

## Workflow

Before changing code, read `README.md`, `TASK.md`, this file, and the relevant
documents. Preserve unrelated user changes. After changes, run formatting,
static checks, focused tests, full tests, migration checks, and `git diff --check`.

Use small Conventional Commits. Never force push, rewrite history, commit `.env`,
or delete production data. Production switching requires a verified backup and
a retained rollback path.
