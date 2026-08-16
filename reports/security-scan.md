# Backend security scan

**Date:** 2026-08-16
**Scope:** `backend/` — 5,574 lines of application code across `app/`, plus dependencies and git history.
**Commit:** `afa4413` plus uncommitted working-tree changes (logging overhaul, `comments.md` fixes).

## Method

| Tool | Version | What it covers |
|---|---|---|
| Bandit | 1.9.4 | Python static analysis for known insecure patterns |
| pip-audit | 2.10.1 | Known CVEs in installed dependencies |
| Ruff (`S`, `ASYNC`, `BLE`) | 0.16.3 | flake8-bandit rules plus async and blind-except checks |
| Manual review | — | Auth design, config, rate limiting, injection surface, secret handling |

Scanners were installed into a throwaway virtualenv so the project venv was left untouched.

---

## Summary

**No critical or high-severity vulnerabilities.** No dependency CVEs, no injection surface, no
secrets in git history, and the authentication design is sound. Automated scanners returned only
false positives and low-severity style findings.

Five issues are worth acting on, all found by manual review rather than by tooling. Two of them
matter specifically because a public deployment is being planned.

| # | Severity | Issue |
|---|---|---|
| 1 | **Medium** | Uploads are fully buffered into memory before the size limit is checked |
| 2 | **Medium** | Rate limiting is not proxy-aware — collapses behind a reverse proxy |
| 3 | **Low–Medium** | No security response headers (HSTS, CSP, `X-Content-Type-Options`) |
| 4 | **Low** | Rate-limit state is in-process and resets on restart |
| 5 | **Low** | `assert` used for runtime invariants; stripped under `python -O` |

---

## Findings

### 1. Uploads are buffered into memory before the size check — Medium

**Where:** `app/api/v1/routers/ai.py:49`, `app/api/v1/routers/imports.py:57`

```python
content = await file.read()          # entire body into RAM, whatever its size
if len(content) > settings.max_upload_bytes:   # limit applied only afterwards
```

The 10 MB limit is enforced *after* the whole upload is already resident. `file.read()` on a
`SpooledTemporaryFile` rolls to disk past a threshold, so this is not an unbounded RAM read in every
case, but the full payload is still materialised as a single `bytes` object by the time the check
runs.

**Failure scenario:** an authenticated user posts a 2 GB file to `/api/v1/ai/analyze-image`. The
process attempts to hold it in memory and is OOM-killed before the limit is ever evaluated. On a
free-tier host with 512 MB this needs no effort at all — a few hundred megabytes will do it, and the
rate limit of 10/minute still permits ten attempts.

**Fix:** check `Content-Length` before reading, and read in bounded chunks, aborting once the limit
is passed:

```python
if (declared := request.headers.get("content-length")) and int(declared) > settings.max_upload_bytes:
    raise PayloadTooLargeError(...)
```

`Content-Length` is client-supplied and can lie, so keep the post-read check as the real guard and
treat the header as a cheap early reject; the chunked read is what closes it properly.

---

### 2. Rate limiting is not proxy-aware — Medium

**Where:** `app/services/rate_limit.py:11`

```python
limiter = Limiter(key_func=get_remote_address, default_limits=[])
```

`get_remote_address` reads the socket peer address. Behind any reverse proxy — nginx in your own
`docker-compose.yml`, or the load balancer in front of Render, Koyeb or an ALB — that is the
*proxy's* address, identical for every client.

**Failure scenario:** two distinct outcomes, both bad. Every user in the world shares one bucket, so
five failed logins from anyone locks `/auth/login` for everybody for a minute — a trivial
denial-of-service. Meanwhile a real attacker is not throttled relative to anyone else, because the
key does not distinguish them.

This is currently latent: it does not bite in local development, and it will bite on the first day
of the deployment being planned.

**Fix:** run Uvicorn with `--proxy-headers` and a trusted `--forwarded-allow-ips`, then key the
limiter on the client address that `X-Forwarded-For` reports. Never trust that header without
pinning which upstream may set it, or the key becomes attacker-controlled and the limit is bypassed
by spoofing.

---

### 3. No security response headers — Low–Medium

**Where:** `app/main.py` (no header middleware), `frontend/nginx.conf` (none set)

Nothing sets `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options` /
`frame-ancestors`, or a Content-Security-Policy.

**Failure scenario:** the app is clickjackable — an attacker frames the deployed site and overlays
it to capture interactions. Absent `nosniff`, a response whose content type is guessed differently
by the browser widens XSS surface. This matters more than usual here because the frontend stores
access and refresh tokens in `localStorage`, where any successful XSS reads them directly; headers
are one of the layers keeping that from happening.

**Fix:** a small middleware in `main.py` for the API, and `add_header` directives in `nginx.conf` for
the static frontend.

---

### 4. Rate-limit state is in-process — Low

**Where:** `app/services/rate_limit.py`

Already documented honestly in that file's docstring, so this confirms rather than discovers it.
Limits reset on every restart and are not shared across workers, so `5/minute` on login is really
"5 per minute per worker, until the next deploy". Acceptable for a demo; a real deployment points
`storage_uri` at Redis.

---

### 5. `assert` used for runtime invariants — Low

**Where:** `app/services/imports/preview.py:88`, `:118` (Bandit B101, Ruff S101)

```python
assert entry is not None
assert document.table is not None
```

Assertions are removed entirely under `python -O`. These are narrowing a type after a check rather
than validating untrusted input, so this is not a security hole — but if the app were ever run
optimised, the failure mode changes from a clear assertion to an `AttributeError` on `None`, which
surfaces as a 500 instead of a handled error.

**Fix:** replace with an explicit `if ... is None: raise` or restructure so the type narrows
naturally.

---

## Checked and clean

These were examined specifically and found sound:

**Dependencies.** pip-audit reports no known vulnerabilities across the full installed set.

**Secrets.** `keys_human_readable.md` (a live Gemini key) and `backend/.env` exist on disk but are
gitignored and **have never been committed** — git history is clean, and no secret-shaped file is
tracked. Worth keeping in mind that the key is real, so avoid `git add -f`.

**Password handling.** Argon2 via `argon2-cffi`, minimum length 10, hashes never logged or returned.
Login hashes a dummy password when the account does not exist, so response timing does not reveal
which emails are registered.

**Tokens.** Access tokens live 15 minutes. Refresh tokens are stored only as SHA-256 hashes, rotate
on use, and are revoked on rotation — a replayed token is rejected. `jwt.decode` pins
`algorithms=[...]`, so the `alg: none` and algorithm-confusion attacks do not apply.

**Production guard.** Startup fails outright if `ENVIRONMENT=production` and `JWT_SECRET` is still
the development default. Bandit's two `S105` "hardcoded password" hits are false positives: one is
that very sentinel, the other is the literal string `"bearer"`.

**Injection.** No string interpolation reaches SQL anywhere. Report metric and dimension names
resolve through the server-side `METRICS` / `DIMENSIONS` registries, and chat tool names through the
`TOOLS` registry, so user- and model-supplied strings are matched against allow-lists rather than
concatenated.

**Authorisation.** Every service function takes the owning `user_id`; there is no by-ID-alone
accessor. Cross-user access returns 404 rather than 403, so the API does not confirm that another
user's records exist. Chat tools cannot express a user identifier at all — the dispatcher injects
it, so no prompt can widen scope.

**Error handling.** The catch-all handler logs the real exception and returns a generic body;
internals and stack traces never reach the client.

**Uploads beyond size.** PDF page count is capped, images have a decompression-bomb guard
(`MAX_DECODED_PIXELS`), content types are allow-listed, and no uploaded bytes are ever persisted.

**Logging.** Secrets are redacted and oversized values truncated in the formatter, so the new log
file cannot accumulate passwords or base64 image data.

**Container.** The backend image runs as a non-root user.

---

## Out of scope

Frontend code was not scanned — you asked for the backend. One cross-cutting note worth carrying
over: tokens are held in `localStorage` (`frontend/src/lib/api.ts`), which is readable by any
successful XSS. Moving to `httpOnly` cookies would need CSRF protection in exchange, so it is a real
trade-off rather than a clear win, but it is the reason finding 3 is worth doing.

`npm audit` on the frontend dependency tree was also not run.

---

## Appendix: raw tool output

### Bandit 1.9.4 — `bandit -r app`

```
[main]	INFO	profile include tests: None
[main]	INFO	profile exclude tests: None
[main]	INFO	cli include tests: None
[main]	INFO	cli exclude tests: None
[main]	INFO	running on Python 3.14.2
Working... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
Run started:2026-08-16 02:58:13.802250+00:00

Test results:
>> Issue: [B105:hardcoded_password_string] Possible hardcoded password: 'dev-only-insecure-secret-change-me'
   Severity: Low   Confidence: Medium
   CWE: CWE-259 (https://cwe.mitre.org/data/definitions/259.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b105_hardcoded_password_string.html
   Location: app/core/config.py:9:21
8	
9	DEFAULT_JWT_SECRET = "dev-only-insecure-secret-change-me"
10	

--------------------------------------------------
>> Issue: [B101:assert_used] Use of assert detected. The enclosed code will be removed when compiling to optimised byte code.
   Severity: Low   Confidence: High
   CWE: CWE-703 (https://cwe.mitre.org/data/definitions/703.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b101_assert_used.html
   Location: app/services/imports/preview.py:34:4
33	    table = document.table
34	    assert table is not None  # guarded by document.kind
35	    return TableSample(

--------------------------------------------------
>> Issue: [B101:assert_used] Use of assert detected. The enclosed code will be removed when compiling to optimised byte code.
   Severity: Low   Confidence: High
   CWE: CWE-703 (https://cwe.mitre.org/data/definitions/703.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b101_assert_used.html
   Location: app/services/imports/preview.py:88:8
87	        entry = row.entry
88	        assert entry is not None
89	        key = (entry.consumed_on, entry.food_name.lower(), round(entry.calories))

--------------------------------------------------
>> Issue: [B101:assert_used] Use of assert detected. The enclosed code will be removed when compiling to optimised byte code.
   Severity: Low   Confidence: High
   CWE: CWE-703 (https://cwe.mitre.org/data/definitions/703.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b101_assert_used.html
   Location: app/services/imports/preview.py:118:8
117	        mapping = _apply_overrides(mapping, date_format, default_meal_type)
118	        assert document.table is not None
119	        rows = apply_mapping(document.table, mapping)

--------------------------------------------------

Code scanned:
	Total lines of code: 5574
	Total lines skipped (#nosec): 0
	Total potential issues skipped due to specifically being disabled (e.g., #nosec BXXX): 0

Run metrics:
	Total issues (by severity):
		Undefined: 0
		Low: 4
		Medium: 0
		High: 0
	Total issues (by confidence):
		Undefined: 0
		Low: 0
		Medium: 1
		High: 3
Files skipped (0):
```

### pip-audit 2.10.1 — installed dependency CVEs

```
No known vulnerabilities found
Name                Skip Reason
------------------- ----------------------------------------------------------------------------------
calorie-tracker-api Dependency not found on PyPI and could not be audited: calorie-tracker-api (0.1.0)
```

### Ruff 0.16.3 — `ruff check app --select S,ASYNC,BLE`

```
S105 Possible hardcoded password assigned to: "DEFAULT_JWT_SECRET"
 --> app/core/config.py:9:22
  |
7 | from pydantic_settings import BaseSettings, SettingsConfigDict
8 |
9 | DEFAULT_JWT_SECRET = "dev-only-insecure-secret-change-me"
  |                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

S105 Possible hardcoded password assigned to: "token_type"
  --> app/schemas/auth.py:44:23
   |
42 |     access_token: str
43 |     refresh_token: str
44 |     token_type: str = "bearer"
   |                       ^^^^^^^^
45 |     expires_in: int = Field(description="Access token lifetime in seconds")
   |

S101 Use of `assert` detected
  --> app/services/imports/preview.py:34:5
   |
32 |     settings = get_settings()
33 |     table = document.table
34 |     assert table is not None  # guarded by document.kind
   |     ^^^^^^
35 |     return TableSample(
36 |         headers=table.headers,
   |

S101 Use of `assert` detected
  --> app/services/imports/preview.py:88:9
   |
86 |     for row in dated:
87 |         entry = row.entry
88 |         assert entry is not None
   |         ^^^^^^
89 |         key = (entry.consumed_on, entry.food_name.lower(), round(entry.calories))
90 |         match = index.get(key)
   |

S101 Use of `assert` detected
   --> app/services/imports/preview.py:118:9
    |
116 |         mapping = provider.infer_table_mapping(_sample(document))
117 |         mapping = _apply_overrides(mapping, date_format, default_meal_type)
118 |         assert document.table is not None
    |         ^^^^^^
119 |         rows = apply_mapping(document.table, mapping)
120 |     else:
    |

Found 5 errors.
```

### Git history — secret exposure check

```
$ git log --all --name-only -- keys_human_readable.md backend/.env
(no output above = never committed)

$ git ls-files | grep -iE "\.env$|key|secret|credential"
(no output above = no secret-shaped files tracked)
```
