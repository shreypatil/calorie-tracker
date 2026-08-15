# Personal Calorie Tracker

A full-stack app for logging meals, setting nutrition goals, and understanding intake over time —
with AI-assisted entry from photos and PDFs, and a chat interface that can drive the whole app.

Full specification: [`requirements.md`](./requirements.md).

> **Status: Phases 1–3a complete.** Auth, goals, entries, listing, the reporting layer, the web app
> and PDF bulk import are built, tested, and runnable. Chat (3b) and photo extraction (3c) are not
> yet built. See [Build status](#build-status).

---

## Quick start

### With Docker

```bash
docker compose up --build
```

The app comes up on <http://localhost:8080>; the API applies its migrations on startup. Interactive
API docs are proxied at <http://localhost:8080/api/v1> and served directly on the api container.

### Locally

```bash
make install    # backend virtualenv + npm install + .env from the example
make migrate    # create the SQLite schema
make seed       # demo account with 30 days of data
make dev        # API on :8000, web app on :5173
```

Then open <http://localhost:5173> and sign in as `demo@example.com` / `demo-password-1234`.

`make help` lists every target. `make api` and `make web` run the two halves separately.

### No API keys required

The app runs fully without any credentials. AI features sit behind a provider interface whose default
implementation is a deterministic stub, so a reviewer can exercise every feature — including PDF
import — on a fresh clone with no account, no key, and no network.

Setting `AI_API_KEY` switches to real inference with no code change. One adapter serves every
provider, because OpenAI, Google Gemini, Groq and a locally-run Ollama all expose an OpenAI-compatible
endpoint — so choosing one is two lines of `.env`:

| Provider | Free? | `.env` |
|---|---|---|
| **Google Gemini** (default) | Free tier, no card | `AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/`<br>`AI_MODEL=gemini-flash-lite-latest` |
| **Groq** | Free tier, no card | `AI_BASE_URL=https://api.groq.com/openai/v1`<br>`AI_MODEL=llama-3.3-70b-versatile` |
| **Ollama** | Free, local, no account | `AI_BASE_URL=http://localhost:11434/v1`<br>`AI_MODEL=llama3.1` · set `AI_PROVIDER=openai_compatible` |
| **OpenAI** | Paid | `AI_BASE_URL=https://api.openai.com/v1`<br>`AI_MODEL=gpt-4o-mini` |

`backend/.env.example` carries all four ready to uncomment.

**Watch the per-model daily cap.** Gemini's free tier limits requests *per model, per day*, and the
limits differ sharply: `gemini-flash-latest` is the sharper reader but allows only ~20 requests/day —
one afternoon of testing exhausts it — so the default is `gemini-flash-lite-latest`, which has a far
larger allowance and handled every fixture correctly. Hitting the cap returns a `429` naming the limit
and suggesting a model change, rather than a generic failure.

---

## Trying it out

With the server running and the seed loaded:

```bash
# Log in
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"demo-password-1234"}' | jq -r .access_token)

# The goal currently in force
curl -s localhost:8000/api/v1/goals/current -H "Authorization: Bearer $TOKEN" | jq

# Last week's dinners, paginated
curl -s "localhost:8000/api/v1/entries?meal_type=dinner&page_size=5" \
  -H "Authorization: Bearer $TOKEN" | jq '{total, has_next, items: [.items[].food_name]}'
```

Or click through <http://localhost:8000/docs>, which is generated from the code and always current.

---

## Architecture

```
backend/app/
  main.py             app factory, middleware, exception handlers
  core/               config, security, deps, errors, pagination, logging
  db/                 engine/session, declarative base, models/
  schemas/            Pydantic request and response models
  services/           all business logic
    reports/          the aggregation layer every report is built on
  api/v1/routers/     HTTP layer only
  ai/                 provider Protocol, stub, and one OpenAI-compatible adapter
  services/imports/   PDF extraction, mapping application, preview, undo
  alembic/            migrations

frontend/src/
  lib/                API client, session, query hooks, formatting
  components/         UI primitives and charts
  pages/              one file per screen
```

Six decisions shape the rest of the codebase:

**Routers are thin; services hold the logic.** Routes parse, authorize, and delegate. This is what
lets the chat interface (Phase 3b) call the *same* `create_entry` the REST API calls, rather than
growing a second, divergent implementation of the app.

**Services take the owning `user_id`, always.** There is no way to fetch or mutate a record by ID
alone — `get_entry(session, user_id, entry_id)` has no single-argument sibling. Isolation therefore
survives someone adding a new route later without thinking about it. Requests for another user's
record return `404`, not `403`, so the API never confirms that other users' data exists.

**Goals are versioned, not mutated.** Each change to a target is a row with its own `effective_from`
date. Without this, changing a calorie target would silently rewrite what every past day had been
measured against, and goal-vs-actual history would become fiction.

**`food_entries` is a fact table.** Anything that might ever be aggregated gets a typed column;
`micros_extra` JSON is display-only and is never aggregated over. When a micronutrient becomes
chart-worthy it is promoted to a real column by migration and registered as a metric.

**A new report is a new caller, not new SQL.** `services/reports/query.py` holds two registries —
`METRICS` (what to sum) and `DIMENSIONS` (what to group by) — and one `aggregate()` function over
them. Every named report is a three-line caller, and `GET /reports/aggregate` exposes the layer
directly, so new report shapes need no backend change at all. Because names resolve through the
registries rather than being interpolated, user input never reaches the query text.

```bash
# "Top foods by calories" — a report nobody wrote code for
curl "localhost:8000/api/v1/reports/aggregate?metrics=calories&group_by=food_name" \
  -H "Authorization: Bearer $TOKEN"
```

The one piece of SQL that SQLite and PostgreSQL genuinely disagree about — truncating a date to its
day, week, or month — is isolated in a single compiled construct in `services/reports/buckets.py`.
Everything else in the reporting layer is written once and runs unchanged on either backend.

**The AI describes the document; our code reads the values.** A PDF food diary has no fixed schema —
column names, ordering, date format and meal vocabulary all vary per file. So the model is shown a
header plus ~15 sample rows and asked for a *mapping*: which column is calories, whether dates are
day-first, whether values are per 100g. Our own code then parses every figure out of the document
using that mapping. A model cannot hallucinate a calorie count it was never asked to produce, and the
call stays the same size whether the diary has 12 rows or 400.

The prose fallback, used only when there is no table at all, is the one place the model transcribes.
There every number it returns is checked to literally appear in the source text; one that doesn't is
dropped and the row flagged. Those rows are never marked ready, so a human sees them all.

Nothing is written until the user confirms. `POST /imports/pdf` returns draft rows and a plain-language
summary of what was understood; committing goes through the same `POST /entries/bulk` that manual
entry uses, tagged as one undoable import batch.

### Cross-cutting behaviour

| Concern | How it works |
|---|---|
| Errors | One `AppError` hierarchy → RFC 9457 `application/problem+json` via a single handler. No route builds an error body. |
| Pagination | One `Page[T]` envelope and one `page`/`page_size` dependency on every list route; `page_size` capped at 100 server-side. |
| Logging | Structured JSON with a request ID on every line, echoed in `X-Request-ID` and in every error body. |
| Auth | Argon2 hashing, 15-minute access tokens, rotating refresh tokens stored only as SHA-256 hashes. |
| Timestamps | A `UtcDateTime` type keeps datetimes timezone-aware even on SQLite, which has no native timezone support. |

---

## The web app

A deliberately quiet interface built on one idea: the discipline of a nutrition-facts panel. Every
number is set in mono tabular figures and right-aligned, micro-labels are uppercase, and hierarchy is
carried by rule weight rather than by shadows or colour. There is no motion anywhere.

The three macro series colours were **validated for colour-vision-deficiency separation** (worst
adjacent pair ΔE 22.7 protan, 20.0 tritan) rather than picked by eye, and every chart with more than
one series carries a text legend, so identity never rests on colour alone. The eleven-nutrient
micronutrient summary is a table with meters rather than a chart — eleven hues nobody can tell apart
would be worse than numbers.

Screens: sign in / register · Today · Entries (filter, paginate, log a meal) · Reports · Goals ·
Import (upload, review, commit, undo).

## Testing

```bash
make test    # 161 backend tests, plus the frontend type check and build
make lint
```

The backend suite covers auth flows including refresh-token rotation and replay, per-resource user
isolation, input validation, filtering, the pagination contract, and error-envelope consistency. Each
test gets its own temporary SQLite file, so tests are order-independent.

Reports have their own focused set against a fixed seeded dataset: every metric × dimension pair in
the registries is exercised, unknown names are rejected, empty days are gap-filled as zeros, week
buckets land on Mondays, and goal-vs-actual is checked against the goal version in force — including
across a mid-week goal change.

Import is tested against four committed PDF fixtures, each standing for a real failure mode — a clean
table, per-100g values with units in the header, a prose diary with no table, and a page with no text
layer. Regenerate them with `python -m tests.fixtures.make_fixtures`. Beyond the happy path, the suite
asserts the things that would be quiet bugs: that a preview writes nothing, that a fabricated number
absent from the source is discarded rather than imported, that undo removes the *entries* and not just
the batch row, and that one user cannot see or undo another's import.

Because these run against the stub provider they need no key and no network. That also means they
prove the pipeline, not the quality of a real model's reading — see the caveat under
[Build status](#build-status).

The UI is checked by driving a real browser:

```bash
npx playwright install chromium   # once
npm run screenshots -- ./shots    # in frontend/, with the app running
```

It signs in as the demo user, walks every page, writes a PNG per screen, and fails loudly on any
console error. `node scripts/import-walkthrough.mjs ./shots <file.pdf>` goes further on the import
flow specifically: upload, re-read with a corrected date format, commit, and undo.

---

## Configuration

Copy `backend/.env.example` to `backend/.env`. Every setting has a working default except in
production, where startup fails if `JWT_SECRET` is still the development value.

### On SQLite

SQLite was chosen so the project runs with zero setup. It is the weakest part of the "production
ready and scalable" requirement — single-writer, not network accessible, awkward to scale out — and
the code is written to make that honest rather than to hide it:

- all access goes through SQLAlchemy, with no SQLite-specific SQL in application code;
- the one dialect-dependent piece will be a single `date_bucket()` helper in the reports layer;
- migrations use Alembic batch mode, so they behave the same on both backends.

Moving to PostgreSQL is a `DATABASE_URL` change plus `make migrate`.

---

## Build status

| Phase | Scope | Status |
|---|---|---|
| 1 | Scaffold, Docker, migrations, error/pagination/logging primitives, auth (FR-7), goals (FR-1), entries CRUD and filtered listing (FR-2, FR-3), seed, tests | **Complete** |
| 2 | Composable aggregation layer, report endpoints, the web app and its four visualizations (FR-4) | **Complete** |
| 3a | AI provider abstraction, PDF bulk import with preview and undo (FR-8) | **Complete** |
| 3b | Conversational chat interface (FR-6) | Not started |
| 3c | AI photo extraction (FR-5) | Not started |
| 4 | Docs, coverage, security review | Not started |

**Verified against live Gemini.** Every fixture has been run end-to-end through the browser with a real
free-tier key: the per-100g table had its basis, serving column and day-first dates all inferred
correctly and scaled to 123/190/118/146 kcal; the prose diary yielded 6 entries with correct dates and
meals; the scanned PDF was rejected with a clear message. The automated suite still runs entirely
against the stub, so `make test` needs no key, no network, and no quota.

Scanned PDFs are detected and rejected with a clear message rather than silently returning zero rows.
`ExtractedDocument` carries `has_text_layer` and the page count so Phase 3c's vision model can pick
them up, which is one branch in `services/imports/preview.py`.

### Endpoints available now

```
POST   /api/v1/auth/register      POST   /api/v1/entries
POST   /api/v1/auth/login         GET    /api/v1/entries
POST   /api/v1/auth/refresh       POST   /api/v1/entries/bulk
POST   /api/v1/auth/logout        GET    /api/v1/entries/{id}
GET    /api/v1/auth/me            PATCH  /api/v1/entries/{id}
                                  DELETE /api/v1/entries/{id}
GET    /api/v1/goals
POST   /api/v1/goals              GET    /api/v1/weights
GET    /api/v1/goals/current      POST   /api/v1/weights
PATCH  /api/v1/goals/{id}
DELETE /api/v1/goals/{id}         GET    /api/v1/reports/aggregate
                                  GET    /api/v1/reports/catalogue
GET    /health                    GET    /api/v1/reports/daily-summary
                                  GET    /api/v1/reports/trend
POST   /api/v1/imports/pdf        GET    /api/v1/reports/macros
GET    /api/v1/imports            GET    /api/v1/reports/micros
DELETE /api/v1/imports/{id}       GET    /api/v1/reports/goal-vs-actual
```
