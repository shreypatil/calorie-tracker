# Personal Calorie Tracker

A full-stack app for logging meals, setting nutrition goals, and understanding intake over time —
with AI-assisted entry from photos and PDFs, and a chat assistant that can drive the whole app.

**Live demo:** <https://shreya-hp.tailf3e298.ts.net/> — sign in as `demo@example.com` /
`demo-password-1234`, which comes preloaded with a month of data.

Full specification: [`requirements.md`](./requirements.md).

---

## Running it locally

**Prerequisites:** Docker, *or* Python 3.12+ and Node 20+.

### With Docker

```bash
docker compose up --build
```

That's the whole setup. The app comes up on <http://localhost:8080> and the API applies its
migrations on startup.

### Without Docker

```bash
make install    # backend virtualenv + npm install + .env from the example
make migrate    # create the SQLite schema
make seed       # demo account with 30 days of data
make dev        # API on :8000, web app on :5173
```

Then open <http://localhost:5173> and sign in as `demo@example.com` / `demo-password-1234`.

`make help` lists every target. `make api` and `make web` run the two halves separately, `make test`
and `make lint` check it, and `make reset` rebuilds the database from scratch.

### No API key required

The app runs fully without any credentials. AI features sit behind a provider interface whose default
implementation is a deterministic stub, so you can exercise every feature — including PDF import,
chat and photo scanning — on a fresh clone with no account, no key, and no network.

To use real inference instead, set `AI_API_KEY` in `backend/.env`. One adapter serves every provider,
because OpenAI, Google Gemini, Groq and a locally-run Ollama all expose an OpenAI-compatible
endpoint, so switching is two lines:

| Provider | Free? | `.env` |
|---|---|---|
| **Google Gemini** (default) | Free tier, no card | `AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/`<br>`AI_MODEL=gemini-flash-lite-latest` |
| **Groq** | Free tier, no card | `AI_BASE_URL=https://api.groq.com/openai/v1`<br>`AI_MODEL=llama-3.3-70b-versatile` |
| **Ollama** | Free, local, no account | `AI_BASE_URL=http://localhost:11434/v1`<br>`AI_MODEL=llama3.1` |
| **OpenAI** | Paid | `AI_BASE_URL=https://api.openai.com/v1`<br>`AI_MODEL=gpt-4o-mini` |

`backend/.env.example` carries all four ready to uncomment. Two things to know: in Docker the key
comes from Compose rather than `backend/.env` (which is deliberately not copied into the image), and
`AI_PROVIDER=auto` silently falls back to the stub when no key is present — so set
`AI_PROVIDER=openai_compatible` explicitly if you want a missing key to be an error rather than
canned answers.

### In-app documentation

Development builds carry a **Docs** tab covering the requirements, API surface, architecture,
features and test inventory. Every page is derived from the thing it documents, so none of it can
drift: requirements from `requirements.md`, tests from pytest, dependency versions from the
manifests, the API surface fetched live from `/openapi.json`. `make docs` regenerates it and fails if
the feature guide names an endpoint the API does not serve.

It is excluded from production builds unless you opt in with `VITE_SHOW_DOCS=true` at build time —
the flag folds to a constant, so the routes and the entire docs chunk are eliminated rather than
merely hidden.

---

## Architecture

```
backend/app/
  main.py             app factory, middleware, exception handlers
  core/               config, security, deps, errors, pagination, logging
  db/                 engine/session, declarative base, models/
  schemas/            Pydantic request and response models
  api/v1/routers/     HTTP layer only
  services/           all business logic
    reports/          the aggregation layer every report is built on
    imports/          PDF extraction, mapping, preview, undo
    chat/             tool registry, argument dispatch, agent loop
    photo/            image normalisation, vision extraction, verification
  ai/                 provider Protocol, stub, one OpenAI-compatible adapter

frontend/src/
  lib/                API client, session, query hooks, formatting
  components/         UI primitives and charts
  pages/              one file per screen
```

A few decisions shape everything else:

**Routers are thin; services hold the logic.** Routes parse, authorize, delegate. This is what lets
the chat assistant's `log_meal` tool call the *same* `create_entry` the REST API calls, so validation,
user scoping and goal versioning cannot drift between the two interfaces.

**Services always take the owning `user_id`.** There is no way to fetch or mutate a record by ID
alone. Isolation survives someone adding a route later without thinking about it, and another user's
record returns `404`, not `403`, so the API never confirms that other users' data exists.

**Goals are versioned, not mutated.** Each change to a target is a row with its own `effective_from`
date. Otherwise changing a calorie target would silently rewrite what every past day had been
measured against, and goal-vs-actual history would become fiction.

**`food_entries` is a fact table.** Anything that might be aggregated gets a typed column;
`micros_extra` JSON is display-only and never aggregated over.

**A new report is a new caller, not new SQL.** `services/reports/query.py` holds two registries —
`METRICS` and `DIMENSIONS` — and one `aggregate()` over them. Named reports are three-line callers,
and `GET /reports/aggregate` exposes the layer directly, so new report shapes need no backend change:

```bash
# "Top foods by calories" — a report nobody wrote code for
curl "localhost:8000/api/v1/reports/aggregate?metrics=calories&group_by=food_name" \
  -H "Authorization: Bearer $TOKEN"
```

Because names resolve *through* the registries rather than being interpolated, user input never
reaches the query text. The one construct SQLite and PostgreSQL genuinely disagree about — truncating
a date to its day, week or month — is isolated in `services/reports/buckets.py`.

### How the AI features stay trustworthy

Every AI feature proposes and waits. Nothing a model produces reaches the database without a person
seeing it first.

**PDF import — the model describes the document, our code reads the values.** A food diary has no
fixed schema, so the model is shown a header plus ~15 sample rows and asked for a *mapping*: which
column is calories, whether dates are day-first, whether values are per 100g. Our own parser then
pulls every figure out of the document. A model cannot hallucinate a calorie count it was never asked
to produce, and the call stays the same size whether the diary has 12 rows or 400. The prose fallback
is the one place the model transcribes — and there, every number it returns must literally appear in
the source text or the row is dropped and flagged.

**The assistant asks to act; it never acts.** Chat drives the whole app through tool calling in a
bounded loop. Tools are a registry of ten thin delegations, not an interpreter. Identity is never a
tool argument — `user_id` comes from the authenticated request, so there is no slot a prompt could
fill, and a test asserts this across the whole registry. Writes stop the loop and become a draft,
executed only by an explicit confirm that re-validates and accepts corrections.

**Photo scanning verifies rather than trusts.** Nothing extracts characters from a photo, so whatever
reads the digits *is* an OCR model — a local engine would add a system dependency, do poorly on real
phone photos of curved packaging, and still not handle estimating a plate. Instead the model returns
the label **verbatim** alongside the structured values, and every figure it reports must appear in
that transcript or it is dropped and flagged. Then the arithmetic is checked: calories should equal
4·protein + 4·carbs + 9·fat. Images are normalised in memory and discarded — EXIF orientation applied
first, a decompression-bomb cap, a downscale to 1568px, and a re-encode that strips GPS tags. No
bytes reach disk.

### Cross-cutting behaviour

| Concern | How it works |
|---|---|
| Errors | One `AppError` hierarchy → RFC 9457 `application/problem+json` via a single handler. No route builds an error body. |
| Pagination | One `Page[T]` envelope and one `page`/`page_size` dependency on every list route; `page_size` capped server-side. |
| Logging | Structured JSON to a rotating file plus readable console text, with a request ID on every line, echoed in `X-Request-ID` and in every error body. Secrets are redacted and oversized values truncated in the formatter, so no call site can leak. `make logs` tails it. |
| Auth | Argon2 hashing, 15-minute access tokens, rotating refresh tokens stored only as SHA-256 hashes. |
| Timestamps | A `UtcDateTime` type keeps datetimes timezone-aware even on SQLite, which has no native timezone support. |

---

## The web app

A deliberately quiet interface built on one idea: the discipline of a nutrition-facts panel. Numbers
are set in mono tabular figures and right-aligned, micro-labels are uppercase, and hierarchy is
carried by rule weight rather than shadows or colour.

Chart colours were **validated for colour-vision-deficiency separation** rather than picked by eye —
`frontend/scripts/validate-palette.mjs` simulates protanopia, deuteranopia and tritanopia and fails
the build below a ΔE threshold. Every multi-series chart also carries a text legend, so identity never
rests on colour alone. The eleven-nutrient micronutrient summary is a table with meters rather than a
chart, because eleven hues nobody can distinguish would be worse than numbers.

Screens: sign in / register · Today · Entries · Reports · Goals · Import · Assistant.

Photo capture sits on the log-a-meal form as two buttons rather than one, because the jobs differ and
saying so is more honest than hiding it: *Scan a label* is transcription that gets checked,
*Estimate nutrition* is judgement that cannot be.

---

## Testing

```bash
make test    # 263 backend tests, plus the frontend type check and build
make lint
```

Each test gets its own temporary SQLite file, so tests are order-independent, and everything runs
against the stub provider — no key, no network, no quota. Coverage spans auth flows including
refresh-token rotation and replay, per-resource user isolation, input validation, the pagination
contract, and error-envelope consistency.

Beyond the happy paths, the suite pins the properties that would otherwise become quiet bugs: that a
preview writes nothing, that a fabricated number absent from the source is discarded rather than
imported, that undo removes the *entries* and not just the batch row, that proposing a write changes
nothing, that no argument model in the tool registry accepts a user identifier, and that a reported
figure absent from a photo's own transcript is dropped. Import is tested against four committed PDF
fixtures, each standing for a real failure mode.

The UI is checked by driving a real browser, which fails loudly on any console error:

```bash
npx playwright install chromium   # once
npm run screenshots -- ./shots    # in frontend/, with the app running
```

---

## Configuration

Copy `backend/.env.example` to `backend/.env`. Every setting has a working default, except in
production where startup fails if `JWT_SECRET` is still the development value.

**On SQLite.** It was chosen so the project runs with zero setup, and it is the weakest part of the
"production ready and scalable" requirement — single-writer, not network accessible, awkward to scale
out. The code is written to make that honest rather than to hide it: all access goes through
SQLAlchemy with no SQLite-specific SQL in application code, the one dialect-dependent piece is a
single `date_bucket()` helper, and migrations use Alembic batch mode. Moving to PostgreSQL is a
`DATABASE_URL` change plus `make migrate`.

---

## Status

**Every functional requirement is built** — auth, goals, entries, the reporting layer, the web app,
PDF bulk import, the conversational assistant and photo extraction.

The AI paths have been verified end-to-end against live Gemini, not just against the stub: import
fixtures inferred their basis, serving column and day-first dates correctly; the assistant answered
an intake question with a figure matching `GET /reports/daily-summary` exactly; a per-100g label was
read correctly with every figure surviving the transcript check. Given a *synthetic* drawing of a
plate the model returned low confidence and a note saying it looked like a graphic rather than real
food — which is exactly what makes the low-confidence warning worth showing.

For the full API surface, run the app and open <http://localhost:8000/docs>, which is generated from
the code and always current, or use the in-app **Docs** tab.
