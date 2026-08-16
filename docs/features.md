# Feature guide

The source of truth for the in-app **Docs → Features** page. `make docs` parses this file into
`frontend/src/docs/generated/features.json` and **verifies it**: every `endpoint:` must exist in the
running API's OpenAPI spec, and every `source:` must exist on disk. A stale reference fails the
build rather than being published.

Format per feature:

```
## Feature name
screen: where it lives
summary: one line
use: how a person operates it
internal: what happens when they do
safeguard: what stops it going wrong  (optional)
endpoint: METHOD /path                (repeatable)
source: path/from/repo/root           (repeatable)
control: Name — what pressing it does (repeatable)
```

---

## Log a meal
screen: Entries → Log a meal
summary: Type a meal by hand and save it, with every nutrient available but only a name required.
use: Open Entries and press Log a meal. Date and meal type default to today and breakfast. Give the food a name, adjust quantity and unit, and fill in whatever figures you have. Micronutrients are collapsed until you expand them, because eleven extra fields would stop anyone logging a bowl of oatmeal.
internal: The form is react-hook-form with a zod schema mirroring the server's `EntryCreate`. On submit, unfilled micronutrients are dropped rather than sent as zero — sending zero would claim the food genuinely contains none. The request goes through `lib/api.ts`, which owns the bearer token, to `create_entry`, which writes one row scoped to the authenticated user.
endpoint: POST /api/v1/entries
source: frontend/src/pages/LogEntryForm.tsx
source: backend/app/services/entries.py
control: Clear — resets every field including the micronutrients, and drops any AI provenance markers
control: Save entry — validates and writes the row

## Estimate nutrition
screen: Entries → Log a meal → Estimate nutrition
summary: Name a dish and the model fills in only the nutrition fields you left alone.
use: Type a food name, optionally a portion and unit, and optionally any figures you already know. Press Estimate nutrition. Fields the model filled are marked with a star; Undo estimate reverts them. The Save button is still what writes anything.
internal: The form tracks where each field's value came from — you, a photo scan, or a previous estimate — because deciding on "is it zero" cannot tell "I left this alone" from "I meant zero". Eligible fields are sent as the `fields` list and everything you typed is sent as `known`, so the estimate is scaled around your figures rather than a generic serving. The service returns values only for the fields that were requested.
safeguard: A value you entered can never be replaced, and that is enforced on the server rather than in the browser — the response simply cannot contain a field the request did not ask for, so a model volunteering extra values cannot overwrite your input.
endpoint: POST /api/v1/ai/estimate-nutrition
source: backend/app/services/nutrition_estimate.py
source: backend/app/schemas/nutrition.py
control: Estimate nutrition — requests values for untouched fields only
control: Undo estimate — restores the values held before the last estimate

## Scan a label or meal photo
screen: Entries → Log a meal → Scan a label / Estimate a meal
summary: Read a product's nutrition panel, or estimate a plate of food, from a photograph.
use: Two buttons rather than one, because the jobs differ. Scan a label transcribes a printed panel; Estimate a meal judges a plate. A single food fills the form directly; several foods become an editable draft table with Add all.
internal: The image is normalised in memory — EXIF rotation applied first, a decompression-bomb cap, downscaled to 1568px and re-encoded, which also strips GPS tags. It is sent inline to the vision model and discarded. Nothing reaches disk or the database.
safeguard: For a label the model returns the panel verbatim, and every figure it reports must literally appear in that transcript or it is dropped and flagged — a plausible invented calorie count is indistinguishable from a correct one by eye. Calories are also checked against 4/4/9 macro arithmetic. A plate has no ground truth to check, so it is labelled an estimate and every figure stays editable.
endpoint: POST /api/v1/ai/analyze-image
source: backend/app/services/photo/prepare.py
source: backend/app/services/photo/verify.py
source: frontend/src/components/photo/ScanControl.tsx
control: Scan a label — transcription mode, figures verified against the panel
control: Estimate a meal — estimation mode, itemised per food
control: Add all — commits the reviewed rows in one batch

## Assistant
screen: Assistant
summary: Drive the whole app in plain language — log meals, set goals, ask about intake.
use: Type a request. Questions are answered directly. Anything that would change data comes back as a draft you Confirm or Discard, and you can edit the figures first.
internal: Tool calling in a bounded loop. The model names a tool and supplies arguments; a server-side registry resolves the name and a Pydantic model validates the arguments before any service runs. Each tool is a thin delegation to the same service function the REST API uses, so the two interfaces cannot drift apart. Conversation history is replayed as prose only — previous tool results are stale and expensive to re-send.
safeguard: Tools that write are never executed inside the loop; they become a pending action that only an explicit confirm dispatches. Identity is not expressible as a tool argument — the dispatcher injects the authenticated user, so no prompt can widen scope to another user's data.
endpoint: POST /api/v1/chat/messages
endpoint: POST /api/v1/chat/actions/{action_id}/confirm
endpoint: POST /api/v1/chat/actions/{action_id}/discard
source: backend/app/services/chat/tools.py
source: backend/app/services/chat/agent.py
source: backend/app/services/chat/dispatch.py
control: Confirm — validates the arguments again and runs the tool; a second press is rejected
control: Discard — marks the draft dead so it can never be confirmed
control: Clear conversation — deletes your transcript; pending drafts die unexecuted

## Import a PDF diary
screen: Import
summary: Bulk-import a food diary exported as a PDF, with a review step and an undo.
use: Choose a PDF. You are shown what was understood — which column meant what, how dates were read, whether values were per 100g — and can correct the date format or default meal and have it re-read without re-uploading. Select the rows you want and import.
internal: The model never reports nutrition figures. It is shown a header and a sample of rows and returns a description of the layout; our own code then parses every value out of the document using that description. A model cannot hallucinate a calorie count it was never asked to produce, and the call is the same size whether the diary has 12 rows or 400.
safeguard: The prose fallback, used only when there is no table at all, is the one place the model transcribes — and there every number is checked to appear in the source text. Committing goes through the same bulk endpoint manual entry uses, tagged as one undoable batch.
endpoint: POST /api/v1/imports/pdf
endpoint: POST /api/v1/entries/bulk
endpoint: DELETE /api/v1/imports/{batch_id}
source: backend/app/services/imports/mapping.py
source: backend/app/services/imports/prose.py
control: Choose a PDF — parses and previews; writes nothing
control: Import N entries — commits the selected rows as one batch
control: Undo — removes the batch and every entry it created

## Reports
screen: Reports
summary: Calorie trend, macro breakdown, goal-vs-actual, micronutrient totals, and a chart you build yourself.
use: Set a date range directly or use a quick range, and choose the time bucket. Build a chart lets you overlay nutrients of your choosing.
internal: Every report is a caller of one composable aggregation layer rather than its own query. Metrics and dimensions resolve through server-side registries, so a new report shape needs no backend change and user input never reaches the query text. The one construct SQLite and PostgreSQL genuinely disagree about — truncating a date to its bucket — is isolated in a single compiled helper.
safeguard: The overlay chart is capped at five series because that is the most that stay mutually distinguishable under all three colour-vision deficiencies; the palette is validated by a script, not chosen by eye. Mixed units get a second axis, and a third unit family is refused rather than drawn misleadingly.
endpoint: GET /api/v1/reports/aggregate
endpoint: GET /api/v1/reports/catalogue
endpoint: GET /api/v1/reports/trend
endpoint: GET /api/v1/reports/goal-vs-actual
source: backend/app/services/reports/query.py
source: backend/app/services/reports/buckets.py
source: frontend/src/components/charts/CustomChart.tsx
control: Quick ranges — sets both dates and the bucket in one press
control: Nutrient pills — toggles a series; disabled with a reason when it would need a third axis

## Goals
screen: Goals
summary: Set nutrition targets that take effect from a date, without rewriting the past.
use: Set targets and the date they start. Past versions remain listed.
internal: Each change is a new row with its own `effective_from` rather than an edit in place. The goal in force on any date is the latest version at or before it.
safeguard: Without versioning, changing a target would silently rewrite what every past day had been measured against and goal-vs-actual history would become fiction.
endpoint: GET /api/v1/goals
endpoint: POST /api/v1/goals
endpoint: GET /api/v1/goals/current
source: backend/app/services/goals.py

## Today
screen: Today
summary: The one question the app exists to answer — what have I eaten today, against my goal.
use: Calories and macros against target, the last fortnight's trend, and a by-meal breakdown. Hover or tab to a meal's item count to see what it contained.
internal: The by-meal detail is preloaded with the day's entries and grouped in the browser, so opening it costs no request.
safeguard: The item popover opens on hover, focus and tap, and closes on Escape — a hover-only tooltip would make the information unreachable by keyboard or on a touchscreen.
endpoint: GET /api/v1/reports/daily-summary
source: frontend/src/pages/Dashboard.tsx
source: frontend/src/components/MealItemsPopover.tsx
control: Log a meal — opens Entries with the form already expanded and scrolled into view
