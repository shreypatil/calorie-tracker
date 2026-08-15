# Personal Calorie Tracker — Requirements Specification

## 1. Overview

The Personal Calorie Tracker is a full-stack application designed to help users monitor, manage, and understand their
daily nutritional intake. Users can log meals across breakfast, lunch, and dinner, set personalized health goals, and
visualize macro and micronutrient trends over time.

Beyond conventional form-based logging, the app offers two assisted entry paths — photographing a nutrition label or a
plate of food, and importing a food diary exported as a PDF — plus a conversational interface that can drive every
action in the app through natural language.

**Audience.** Individuals tracking their own intake. Every user's data is private to them.

**Definition of done.** All eight functional requirements below satisfy their acceptance criteria; all six
non-functional requirements hold; a reviewer can clone the repository, run one command, and exercise every feature
including the AI ones without supplying any API keys.

---

## 2. Decision log

| Area | Decision | Rationale |
|---|---|---|
| Purpose | Take-home / portfolio demo | Prioritizes complete coverage of the requirements, readable code, and a frictionless local run over operational depth. |
| Backend | Python 3.12 + FastAPI | Pydantic v2 validation satisfies NFR-6 natively, auto-generated OpenAPI docs are directly reviewable, and dependency injection keeps auth and DB session wiring clean. |
| Frontend | React 19 + TypeScript + Vite + Tailwind | Mainstream, fast dev loop, and a clean separation from the backend as NFR-1 requires. |
| Charts | Recharts | Small API, sensible defaults, covers the line / stacked-bar / pie cases the reports need. |
| Database | SQLite via SQLAlchemy 2.0 + Alembic | Zero setup for whoever runs the project. All access goes through the ORM with no SQLite-specific SQL outside one helper, so PostgreSQL is a connection-string change plus a migration run. See §7.1 for the honest limitation. |
| Auth | Own JWT auth (email + password) | No external service or keys needed to run the project; argon2 hashing with rotating refresh tokens. |
| AI provider | Provider-agnostic, stub by default | The app must run with no API key. A deterministic stub backs every AI feature; setting `AI_API_KEY` upgrades to real inference with no code change. One OpenAI-compatible adapter serves Gemini, Groq, Ollama and OpenAI alike, so choosing a provider is two lines of `.env`. |
| Nutrition data | AI + manual entry only | No external food database initially. A `FoodLookupSource` seam exists so a free source (Open Food Facts, USDA FoodData Central) can be added later without touching routes or models. |
| Micronutrients | Fixed typed columns + JSON overflow | The common micros are typed columns so they can be aggregated and charted; anything extra the AI extracts lands in a display-only JSON field. |
| Reports | One composable aggregation layer | Reports are expected to grow well past the required set, so a new report must mean a new caller, not new SQL. See FR-4 and §5.3. |
| Uploads | Processed in memory, never stored | The extracted values are the only durable output; the user confirms them before anything is written. No job table, no queue, no stored bytes. |
| Chat | One conversation per user | Chat is a control surface for the app, not a messaging product. Multi-session history would be unused complexity. |
| Chat actions | Tool calling through a server-side registry | The model names a tool and supplies arguments; it never reaches the database. Names resolve through a registry and arguments are validated against a schema before any service runs, so the surface the model can reach is exactly what was deliberately exposed. |
| Chat writes | Proposed, then confirmed | Reads answer directly, but anything that changes data is returned as a draft and applied only on an explicit confirm. With no food database, logged nutrition figures are the model's estimate — acceptable only because a person reviews and can correct every number before it is written. |
| Sequencing | Phased: core → reports → AI | Each phase ends runnable and demoable. |

---

## 3. Functional requirements

### FR-1 — Goal setting

Users can set and manage personal health goals: daily calorie target, protein/carb/fat targets, per-micronutrient
targets, and a weight goal.

Goals are **versioned by `effective_from` date** rather than mutated in place. The goal in force on any given date is
the most recent version at or before that date.

**Acceptance criteria**
- A user can create a goal version, list their goal history, and fetch the goal currently in force.
- Editing targets creates or amends a version; it never silently rewrites what past days were measured against.
- A report for a past date compares against the goal that was in force on that date, not today's goal.
- All targets are optional individually; numeric targets must be non-negative.
- Users can log their weight over time so the weight goal has an actual to compare against.

### FR-2 — Meal entry

Users can create food entries grouped by meal type (Breakfast, Lunch, Dinner, Snacks) with a food item name, quantity,
and nutritional values (calories, macros, micros).

**Acceptance criteria**
- An entry captures: meal type, food name, quantity and unit, calories, protein/carbs/fat, optional micronutrients,
  the date consumed, and how it was created (manual, photo, chat, or PDF import).
- Micronutrients from the fixed set are stored in typed fields; any additional micronutrient extracted by AI is kept in
  a display-only overflow field.
- All numeric fields are validated as non-negative; meal type must be one of the four allowed values.
- An entry dated in the future is rejected.
- An entry belongs to exactly one user and exactly one calendar date.
- Entries can be read, updated, and deleted individually, and created in bulk.

### FR-3 — Time-range listing

Users can list their food entries within a specified time range, filterable by date and meal type.

**Acceptance criteria**
- The list endpoint accepts `date_from`, `date_to`, `meal_type`, and a free-text food-name filter, in any combination.
- Results are paginated (NFR-3) and returned in a stable, deterministic order.
- A user only ever sees their own entries; requesting another user's entry returns 404, not 403, so the endpoint does
  not confirm the existence of other users' data.

### FR-4 — Nutrition reports and graphs

The app displays visual reports: weekly calorie intake trend, macronutrient breakdown by day/week, micronutrient
summary, and goal-vs-actual comparison.

Because reports are expected to grow beyond this initial set, they are built on a **single composable aggregation
layer** (§5.3) rather than one hand-written query per chart.

**Acceptance criteria**
- The four required visualizations render from real logged data.
- Goal-vs-actual uses the goal version in force on each date (FR-1).
- Days within a requested range that have no entries appear as zeros, so trend lines have no gaps.
- A generic aggregation endpoint exposes metric × dimension combinations directly, so new reports need no backend change.
- Only metric and dimension names from the server-side registries are accepted; anything else is rejected.

### FR-5 — AI-powered calorie extraction

Users can upload a photo of a product nutrition label or a plate of food; the app extracts nutritional information and
pre-fills the entry form.

**Acceptance criteria**
- The upload is analyzed and returns a **draft entry** — nothing is written to the database until the user confirms.
- The draft populates food name, quantity, calories, macros, and any micronutrients the model identified.
- The uploaded image is processed in memory and discarded; no image bytes are persisted anywhere.
- Uploads are validated for content type and size before processing.
- With no API key configured, the stub provider returns deterministic draft data so the flow is fully exercisable.
- A provider failure surfaces a clear, actionable error rather than a stack trace or a silently empty form.

### FR-6 — Conversational chat interface

An LLM-powered chat interface lets users perform all app actions through natural language — logging meals, checking
goals, asking nutritional questions, and getting weekly summaries — without touching traditional UI controls.

**Acceptance criteria**
- The chat can log a meal, query entries, read and update goals, and produce a weekly summary, via tool calling.
- Chat tools invoke **the same service functions** the REST endpoints use, so behaviour and validation cannot diverge
  between the two interfaces.
- Each user has one persistent conversation that survives a page refresh, and can clear it.
- Tools are scoped to the authenticated user; the chat cannot read or modify another user's data under any prompt.
  The authenticated user's ID is supplied by the server and is never a tool argument, so no prompt can widen scope.
- **No tool that writes is executed by the conversation.** A change is returned as a proposed action and applied only
  by an explicit confirmation, which re-validates the arguments and accepts corrections to them first.
- Read tools resolve within a bounded number of steps; the turn always ends with a reply rather than an error.
- With no API key configured, the stub provider returns deterministic tool calls so the flow is fully exercisable.

### FR-7 — Multi-user support

Multiple independent users can sign up, log in, and maintain their own private data.

**Acceptance criteria**
- Registration, login, token refresh, logout, and "who am I" are all supported.
- Passwords are hashed with argon2 and never logged or returned.
- Access tokens are short-lived; refresh tokens rotate on use, are stored only as hashes, and can be revoked.
- Every data query is scoped by the authenticated user's ID **in the service layer**, not only at the route.
- Test coverage asserts, per resource type, that user A cannot read or modify user B's data.

### FR-8 — Bulk import via PDF

Users can upload a food diary or nutrition history exported as a tabular PDF; entries are parsed and imported.

**Acceptance criteria**
- The PDF is parsed and returns **draft rows** for review — nothing is written until the user confirms.
- The review UI shows parsed rows, flags rows that failed validation, and lets the user correct or drop them.
- Confirmed rows are written in one bulk operation, recorded as a single import batch so the whole import can be undone.
- The PDF is processed in memory and discarded; no file bytes are persisted.
- Uploads are validated for content type, size, and page count before processing.
- A partially parseable PDF imports the rows it could read and reports the rows it could not, rather than failing whole.

---

## 4. Non-functional requirements

### NFR-1 — API/frontend separation
The frontend contains no server-side data access. It communicates with the backend exclusively over HTTP APIs under
`/api/v1`. The backend is independently runnable and its OpenAPI schema fully describes the contract.

### NFR-2 — Persistence
All users, goals, food entries, weight logs, import batches, and chat messages are persisted in the database. Schema
changes are applied through Alembic migrations, never ad-hoc DDL.

### NFR-3 — Pagination
Every list endpoint is paginated using one shared envelope and the same `page` / `page_size` parameters. `page_size` is
capped server-side. No endpoint can return an unbounded result set.

### NFR-4 — Security
Argon2 password hashing; short-lived access tokens with rotating, revocable, hash-stored refresh tokens; user scoping
enforced in the service layer; rate limiting on authentication and AI endpoints; upload content-type sniffing and size
limits; a CORS allowlist from configuration; secrets supplied only via environment variables with a committed
`.env.example` and a gitignored `.env`.

### NFR-5 — Clean, modular code
Routers parse, authorize, and delegate; all business logic lives in the service layer; models and schemas are separate.
Names describe intent. The AI provider, and the future external nutrition source, sit behind explicit interfaces so
implementations can be swapped without touching callers.

### NFR-6 — Error handling and validation
All input is validated by Pydantic schemas at the boundary. A single application error hierarchy is mapped to RFC 9457
`application/problem+json` responses by one exception handler, so no route hand-builds an error body. Every response
and every log line carries a correlating request ID. External-service failures degrade to a clear message.

---

## 5. Data model

### 5.1 Entities

**`users`** — `id` (UUID), `email` (unique, lowercased), `password_hash`, `display_name`, `created_at`, `updated_at`

**`refresh_tokens`** — `id`, `user_id`, `token_hash`, `expires_at`, `revoked_at`
Only hashes are stored; tokens rotate on use.

**`goals`** — `id`, `user_id`, `effective_from` (date), `calorie_target`, `protein_g`, `carbs_g`, `fat_g`,
`weight_target_kg`, `micro_targets` (JSON), `created_at`
Versioned, per FR-1. The goal in force on a date is the latest version at or before it.

**`food_entries`** — `id`, `user_id`, `consumed_on` (date), `consumed_at` (nullable datetime), `meal_type`
(breakfast | lunch | dinner | snack), `food_name`, `quantity`, `unit`, `calories`, `protein_g`, `carbs_g`, `fat_g`,
typed micronutrient columns, `micros_extra` (JSON), `source` (manual | photo | chat | pdf),
`source_ref` (→ `import_batches.id`), `notes`, `created_at`, `updated_at`

Typed micronutrient columns: `fiber_g`, `sugar_g`, `sodium_mg`, `potassium_mg`, `calcium_mg`, `iron_mg`,
`cholesterol_mg`, `vitamin_a_mcg`, `vitamin_c_mg`, `vitamin_d_mcg`, `vitamin_b12_mcg`.

Indexed on `(user_id, consumed_on)` and `(user_id, consumed_on, meal_type)` — every list and report query leads with them.

> **Design rule.** `food_entries` is a fact table: anything that might ever be aggregated gets a typed column, and
> `micros_extra` is display-only. When a micronutrient becomes chart-worthy it is promoted to a real column by migration
> and registered as a metric. Aggregation never reaches into JSON. This is what keeps future reports cheap to add.

**`weight_logs`** — `id`, `user_id`, `logged_on`, `weight_kg`

**`import_batches`** — `id`, `user_id`, `filename`, `row_count`, `created_at`
Written at commit time only, so `source_ref` resolves and an import can be undone in one delete. No status field, no
queue, no stored file.

**`chat_messages`** — `id`, `user_id`, `role`, `content`, `tool_calls` (JSON), `created_at`; indexed `(user_id, created_at)`
One active conversation per user. If multi-session is ever wanted, a nullable `session_id` column is a non-breaking addition.

### 5.2 Shared envelopes

Pagination, used by every list endpoint:

```json
{ "items": [], "page": 1, "page_size": 25, "total": 137, "has_next": true }
```

Errors, RFC 9457 `application/problem+json`:

```json
{ "type": "...", "title": "...", "status": 422, "detail": "...", "errors": [], "request_id": "..." }
```

### 5.3 Aggregation layer

Reports are served by one composable function over two server-side registries:

```python
METRICS    = {"calories": ..., "protein_g": ..., "carbs_g": ..., "fat_g": ..., "entry_count": ...}
DIMENSIONS = {"day": ..., "week": ..., "month": ..., "meal_type": ..., "source": ..., "food_name": ...}

def aggregate(user_id, metrics: list[str], group_by: list[str], filters) -> list[Row]
```

- Each named report endpoint is a thin caller. Adding a metric or dimension is one registry entry.
- Registry lookup by name means user input never reaches the query text.
- A single `date_bucket(granularity)` helper is the only dialect-specific SQL in the codebase.
- Gap-filling happens after the query, so charts have no holes.
- If aggregation ever gets slow, a `daily_nutrition_totals` rollup can be routed to inside `aggregate()` with no
  caller changes. Not built initially.

---

## 6. API contract

All endpoints live under `/api/v1`. All list endpoints are paginated per NFR-3.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register` · `POST /auth/login` · `POST /auth/refresh` · `POST /auth/logout` · `GET /auth/me` |
| Goals | `GET /goals` · `POST /goals` · `GET /goals/current` · `PATCH /goals/{id}` · `DELETE /goals/{id}` |
| Entries | `POST /entries` · `GET /entries` (`date_from`, `date_to`, `meal_type`, `q`) · `GET/PATCH/DELETE /entries/{id}` · `POST /entries/bulk` |
| Weights | `GET /weights` · `POST /weights` |
| Reports | `GET /reports/aggregate` · `GET /reports/daily-summary` · `GET /reports/trend` · `GET /reports/macros` · `GET /reports/micros` · `GET /reports/goal-vs-actual` |
| AI | `POST /ai/analyze-image` → draft entry, nothing persisted |
| Imports | `POST /imports/pdf` → draft rows, nothing persisted; commit via `POST /entries/bulk` |
| Chat | `GET /chat/messages` · `POST /chat/messages` → reply plus any proposed actions, nothing persisted beyond the transcript · `POST /chat/actions/{id}/confirm` · `POST /chat/actions/{id}/discard` · `DELETE /chat/messages` |

---

## 7. Out of scope

- Barcode scanning
- Social features, sharing, or following
- Native mobile applications
- Recipe building and meal planning
- Exercise logging and calories burned
- External food database lookup — deferred behind the `FoodLookupSource` interface
- Multi-session chat history
- Stored uploads and async/queued job processing

### 7.1 Known limitation

SQLite is the weakest part of the "production ready and scalable" requirement: it is single-writer, not network
accessible, and awkward to scale horizontally. It was chosen deliberately so a reviewer can run the project with zero
setup. The codebase mitigates this rather than hides it — all access is through SQLAlchemy, the only dialect-specific
SQL is one date-bucketing helper, and migrating to PostgreSQL is a connection-string change plus a migration run.

---

## 8. Glossary

| Term | Meaning |
|---|---|
| **Meal type** | One of breakfast, lunch, dinner, snack. Every entry has exactly one. |
| **Macro** | Macronutrient: protein, carbohydrate, or fat. |
| **Micro** | Micronutrient: a vitamin or mineral, plus fiber, sugar, and cholesterol as tracked here. |
| **Goal version** | A row in `goals` with an `effective_from` date. The version in force on a date is the latest one at or before it. |
| **Draft entry / draft rows** | Nutritional data extracted from a photo or PDF, returned to the client for review. Not persisted until the user confirms. |
| **Proposed action** | A change the chat assistant has asked to make, held against the message that proposed it. It carries the validated arguments it would run with, and does nothing until confirmed or discarded. |
| **Tool** | One named, schema-validated operation the chat assistant may request. Each is a thin delegation to the same service function the REST API uses. |
| **Import batch** | A record of one confirmed PDF import, linking the entries it created so the import can be undone. |
| **Metric / dimension** | The measures and groupings in the reports registries — what is summed, and what it is grouped by. |
