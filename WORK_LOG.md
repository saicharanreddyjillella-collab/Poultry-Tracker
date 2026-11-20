# Work Log — Section 3 (Flock Performance & Benchmarking)

Implementation loop: implement → write tests → run → fix+log any bug → commit.
Order requested: 3.1, 3.3, 3.4, 3.2, 3.5, 3.6.

## 3.1 — EPEF performance index  ✅ DONE
- Added `avg_sold_weight_kg` and `epef` properties to `Flock` (models.py).
  - EPEF = (Livability% × Avg live weight kg × 100) / (Age days × FCR).
  - Returns None until flock is closed and has sales (needs final weight + FCR).
- Exposed `epef` + `avg_sold_weight_kg` on FlockSerializer & FlockListSerializer,
  and in the `flock_cumulative` API payload.
- Frontend: EPEF stat card on FlockDetail (shown when present).
- Tests: `core/tests/test_performance.py` — 8 tests (avg weight, EPEF value
  429.6 hand-verified, active/no-sales None, monotonicity, API exposure).
- Result: 8/8 passed. No migration needed. Frontend builds clean.
- Bugs found: none.

## 3.3 — Culling separate from mortality  ✅ DONE
- Added `DailyEntry.cull_count` field (migration 0020) + `Flock.total_culls`
  and `Flock.cull_percentage` properties.
- `live_birds` now subtracts culls: chicks - mortality - culls - sold.
- Mortality % stays deaths-only (comparable); culls reported separately.
- API: cull_count writable on daily entries (serializer __all__);
  total_culls + cull_percentage on both Flock serializers; total_culls,
  daily_culls, cumulative_culls and corrected live_birds in
  flock_cumulative.
- Frontend: Culls input on the daily-entry form; Culls stat card on
  FlockDetail.
- Tests: 7 new in test_performance.py (TestCulling).
- Result: 15/15 performance tests pass; migration consistent; FE builds.
- Bug/decision registered: BUG-001 (see below) — billing engine's
  live_birds does NOT yet subtract culls. Left unchanged deliberately
  (money-affecting); needs user decision before touching settlement.


## 3.4 — Daily bird-population reconciliation  ✅ DONE
- System has no bird transfers (only feed transfers), so the identity is
  opening(chick_count) - mortality - culls - sold = closing.
- `Flock.reconciliation` property returns opening/mortality/culls/sold/
  accounted/closing + is_balanced (closing >= 0) + overcount. Flags
  data-entry errors where losses+sales exceed birds placed.
- Exposed on both Flock serializers and in flock_cumulative payload.
- Frontend: red "Population mismatch" banner on FlockDetail when unbalanced
  (new .alert-banner-danger style).
- Tests: 5 new (TestReconciliation). 37/37 pass; no migration; FE builds.
- Bugs: none.

## 3.2 — Breed-standard weight variance  ✅ DONE
- Backend `Flock.weight_vs_standard` property: latest body-weight entry vs
  Cobb-400 standard for that age; returns day/actual/standard/variance_g/
  variance_pct/status (on_track within +/-3%, else above/below). None if no
  weight recorded. Authoritative (usable in API + future report exports),
  not just client-computed.
- Exposed on both Flock serializers + flock_cumulative summary.
- Frontend: "Weight vs Target" stat card (color by status); existing
  per-entry comparison table upgraded to the same +/-3% band with an
  "On track" state (new .weight-on_track style).
- Tests: 6 new (TestWeightVsStandard). 43/43 pass; no migration; FE builds.
- Bugs: none.

## 3.5 — Unified performance scorecard  ✅ DONE
- `Flock.scorecard` property composes available metrics into component
  scores (0-100) and an overall rating (Excellent>=85 / Good>=70 /
  Fair>=50 / Poor). Components: livability (always), weight-vs-target
  (once weighed), EPEF + FCR (closed flocks). Surfaces farmer_grade from
  the bill when one exists. Works for active and closed flocks.
- Exposed on both Flock serializers + flock_cumulative.
- Frontend: scorecard panel at top of FlockDetail — rating, overall score,
  grade, and per-component bars (new .scorecard styles).
- Tests: 6 new (TestScorecard); hand-verified 100/Excellent, 83.5/Good,
  Poor cases. 49/49 pass; no migration; FE builds.
- Bugs: none.

## 3.6 — Water:feed ratio + deviation alert  ✅ DONE
- DailyEntry.water_feed_ratio (L water / kg feed) + water_feed_status
  ('low' <1.2, 'high' >2.5, else 'normal'; None when no feed). Band
  constants WATER_FEED_LOW/HIGH.
- Flock.water_alerts lists flagged entries (date/day/ratio/status/water/
  feed), most recent first.
- Exposed: per-entry ratio+status in cumulative rows; water_alerts in
  summary; water_alerts on both Flock serializers.
- Frontend: 💧 water-alert banner on FlockDetail when any day is out of band.
- Tests: 7 new (TestWaterFeedRatio). 56/56 pass; no migration; FE builds.
- Bugs: none.

---
## Registered bugs / decisions
### BUG-001 — Billing engine ignores culls in live-bird count  [RESOLVED 2026-11-14]
`core/billing.py` computes `live_birds = chicks - total_mortality -
total_sold_birds` (no culls). Now that culls are tracked separately, culled
birds are currently counted as "live", which affects:
  - `admin_cost` (admin_birds = sold + live) → slightly overstated
  - shortage recovery (expected_live vs accounted) → may mis-flag shortage
Options for Sai Charan to decide:
  (a) Treat culls as accounted losses: live_birds = chicks - mortality -
      culls - sold (consistent with the model). Culls then neither inflate
      admin cost nor trigger shortage.
  (b) Treat culls as shortage/recoverable (grower answerable for them).
  (c) Make it a per-farm flag.
RESOLUTION (user decision): treat culls as mortality. billing.py now folds
cull_count into total_mortality, so live_birds, admin cost and shortage all
count culls as losses; first-week excess-mortality and negligence recoveries
also count culls. A flock with N deaths bills identically to one with the same
N split across deaths + culls (verified by test).
Also ported the full bill-engine test suite to main (core/tests/test_billing.py,
17 tests) + 3 cull-as-mortality tests. Suite now 32 tests, all passing.

### BUG-002 — data.py (release split) uses Sum without importing it  [RESOLVED 2026-11-14]
Found while cherry-picking 3.1/3.3 to release/feeds-only: the earlier
Feeds-only split of core/views/data.py left `Sum(...)` calls in the CRUD
module (lines creating/validating daily entries) without
`from django.db.models import Sum`. This is a latent 500 on daily-entry
create — only surfaced now because the new cull API test exercises that
path. Fixed by adding the import on release/feeds-only. (main's data.py was
never split, so main was not affected.)

---
## Section 3 complete — all 6 items done (3.1, 3.3, 3.4, 3.2, 3.5, 3.6). 2 bugs found & fixed (BUG-001, BUG-002).

---
## Section 2 (compliance)

### 2.2 — Grower PAN + entity-type master  ✅ DONE
- Farm.pan + Farm.entity_type (individual/huf/firm/company/llp/fpo/other).
  Helpers: has_valid_pan (PAN regex), is_individual_huf, tds_rate_pct
  (1% Individual/HUF, 2% others).
- FarmSerializer validates PAN format (normalised to upper); exposes
  has_valid_pan + tds_rate_pct.
- FarmForm: Grower Entity Type dropdown + PAN input.

### 2.1 — TDS on grower payments (Section 194C)  ✅ DONE
Policy (per CBDT Circular 4/2017; user decisions):
- Base = net payable to farmer (growing charges + incentive − recoveries);
  free-issued chicks/feed excluded.
- Rate by entity type: 1% Individual/HUF, 2% others. No-PAN is only FLAGGED
  (rate NOT bumped to 20%, bill NOT blocked) — per user decision.
- Thresholds (₹30k single / ₹1 lakh FY aggregate) behind a BillConfig flag
  apply_tds_thresholds (default on); apply_tds master switch (default on).
- billing.py computes tds_rate_pct, tds_amount, amount_paid, tds_pan_missing;
  FY aggregate summed from prior bills (Apr–Mar). config_snapshot records
  rate/entity/pan.
- Bill fields + BillConfig fields (migration 0021). BillView shows
  "Less: TDS @ x%", "Amount Paid (after TDS)", and a PAN-missing warning.
- Tests: core/tests/test_tds.py (11). Full suite 67 pass; FE builds.
- Bugs: none.

NOTE: tax rules — verify rates/thresholds with a CA before go-live.

---
## Section 1 (settlement correctness)

### 1.2 — Feed-lot reconciliation  ✅ DONE
- Flock.feed_reconciliation: dispatched (delivered orders + transfers in −
  transfers out) vs consumed (daily entries), per feed type + total.
  variance = dispatched − consumed; status balanced / over_dispatched
  (possible diversion or unused stock) / under_dispatched (under-recorded
  dispatch / mill under-fill, flatters FCR). Tolerance from BillConfig
  (feed_reconciliation_tolerance_pct, default 5%), migration 0022.
- Exposed on both Flock serializers + flock_cumulative.
- Frontend: "Feed Dispatched vs Fed" stat card on FlockDetail + a feed-
  variance warning inside the Close & Generate Bill modal (surfaces the
  variance before the payment run).
- Tests: core/tests/test_feed_recon.py (9). Full suite 76 pass; FE builds.
- Bugs: none.

### 1.1 — FCR benchmark band premium/deduction  ✅ DONE
Design (user decisions): keep BOTH FCR mechanisms, each its own farm flag;
per-kg unit; stepped by 0.1 FCR.
- New Farm.fcr_benchmark_enabled (default off), independent of the existing
  recovery_fcr (region-average). Both can run together by choice.
- BillConfig: fcr_benchmark (1.75), fcr_benchmark_tolerance_pct (5%),
  fcr_premium_per_kg_per_step (0.3), fcr_deduction_per_kg_per_step (0.3),
  fcr_benchmark_max_adjustment_per_kg (2.0). Migration 0023.
- billing.py: signed fcr_benchmark_adjustment (+premium below band /
  −deduction above band, stepped per 0.1 FCR, capped), folded into
  gross_payable. Bill.fcr_benchmark_adjustment field.
- Close modal: FCR Benchmark toggle (close view flag_fields). BillView:
  "FCR Benchmark Premium/Deduction" line.
- Tests: TestFcrBenchmarkBand (7); values hand-verified (+234.38 beat,
  −536.25 miss, 0 on-band, 125.00 capped). Full suite 83 pass; FE builds.
- Bugs: none.

### 1.5 — Pay basis ₹/bird vs ₹/kg  — NOT NEEDED
User: pay is ALWAYS per kg. No ₹/bird option required; growing charges and
the FCR benchmark already work per kg. No work item.

### 1.3 — Catastrophic-loss / partial-closure  — SKIPPED (user decision)
User: "keep it as normal, no change required." Disease/partial closures are
billed via the normal close flow for now; no separate disease-event path,
recovery waiver, or vet-certificate capture built. Revisit if needed later.

---
## Section A (grower-facing) — features

### A3 — Document repository  ✅ DONE
- Document model: FileField (upload_to by farm/flock), doc_type
  (agreement/kyc/bank/vet_certificate/invoice/other), title, notes,
  uploaded_by/at; links to Farm OR Flock (migration 0024). owning_farm
  helper resolves farm via flock.
- Media wired: MEDIA_URL/ROOT + 10MB upload cap in settings; urls serves
  media in DEBUG; nginx /media/ location added (prod); backend/media
  gitignored. docker-compose already had the media_files volume.
- API: DocumentViewSet (multipart upload, list filtered by farm/flock,
  delete), CanAccessDocument permission (reads open to authed; writes
  follow owning-farm edit rights; supervisors see only their farms' docs).
  documentAPI in client.js.
- Frontend: reusable DocumentsSection component (upload form + list + view/
  delete) on FarmDetail and FlockDetail, gated by canEditFarm.
- Storage decision: local media volume (user asked re OneDrive — advised
  against as an app backend; local now, S3/Spaces as the later upgrade path).
- Tests: core/tests/test_documents.py (10). Full suite 93 pass; FE builds.
- Bugs: none.

---
## Section F (planning)

### F1 — Feed requirement forecast  ✅ DONE
Design (user): all active flocks, 4-week default horizon, by week + phase;
standard intake curve (calibrate-from-history later); apply standard
mortality decline.
- standards.py: DAILY_FEED_INTAKE_G (g/bird/day by age) + get_daily_feed_intake
  (interpolated, clamped) + get_feed_phase (BPSC 0-10 / BSC 11-21 / BFP 22+).
- views feed_forecast(): per active flock, per future day, birds alive
  (declining by standard daily mortality = standard_mortality_pct/42) ×
  intake/bird → kg, attributed to phase, bucketed into weeks. Returns weekly
  (per-phase kg+bags), totals, and per-flock breakdown. weeks param (1-12,
  default 4). Route /api/reports/feed-forecast/.
- Frontend: FeedForecast page (horizon selector, summary cards, by-week and
  by-flock tables) + "Feed Forecast" nav link.
- Tests: test_feed_forecast.py (11). Full suite 104 pass; no migration; FE builds.
- Bugs: none.

### F4 — Owner BI dashboard  ✅ DONE
Design (user): all four sections — active-cycle overview, region/period
summary, performance leaderboard, alerts feed.
- owner_dashboard view (read-only aggregation): overview counts; active_cycle
  rows (age/live/phase/mortality/scorecard rating); region_summary from
  closed+billed flocks in the period (placed/sold/avg FCR/EPEF/mortality/
  settlement paid); leaderboard top/bottom by EPEF; alerts feed (stale data,
  population mismatch, weight-below, feed variance, water). period_days param
  (default 90). Route /api/reports/owner-dashboard/.
- Frontend: OwnerDashboard page (period selector, summary cards, alerts list,
  active-cycle table, leaderboard, region table) + "Owner View" nav link.
  New CSS: .badge, .alert-row*, .leaderboard-grid.
- Tests: test_owner_dashboard.py (7). Full suite 111 pass; no migration; FE builds.
- Bugs: none.

### F3 — Live-flock break-even projection  ✅ DONE
Design (user reframe): instead of a hypothetical form, project break-even for
every LIVE flock at current feed rates — a proxy for what a new placement
breaks even at.
- break_even_projection view: per active flock, feed-to-finish = consumed +
  remaining intake (standard curve, birds declining by standard mortality) to
  a finish age (default 42); total cost = chick + feed(kg × current rate) +
  medicine + admin; projected weight = projected-live × standard finish weight;
  cost/kg = total/weight = break-even price. Avg across flocks. finish_age
  param. /api/reports/break-even/.
- Frontend: BreakEven page (summary + per-flock table) + "Break-even" nav link.
- Tests: test_break_even.py (8). Full suite 119 pass; no migration; FE builds.
- FOLLOW-UP: added a pooled/blended break-even across ALL live flocks
  (total cost / total projected weight — the true weight-weighted figure,
  not the mean of per-flock rates) + pooled totals (cost, weight, feed,
  birds). Shown as the lead card on the page. +4 tests (TestBlendedBreakEven).
- Bugs found & fixed (both in the new code, caught by tests):
  BUG-003 Decimal*float in cost calc (coerced config rates via D());
  BUG-004 ROUND_HALF_UP not imported in data.py (added). NOTE for release
  cherry-pick: ensure ROUND_HALF_UP import exists in reports.py too.

### F2 — Multi-cycle farm performance trends  ✅ DONE
Design (user): on the farm detail page; track FCR, EPEF, livability,
mortality%, cost/kg, grade, settlement paid across cycles.
- farm_performance_history(farm_id) view: closed flocks in placement order,
  each with its metrics (from model props + bill); averages per metric;
  trend direction (first vs last non-null, direction-aware: lower FCR/cost/
  mortality = improving, higher EPEF/livability = improving).
  /api/farms/<id>/performance-history/.
- Frontend: FarmPerformanceHistory component (averages w/ trend badges +
  per-cycle table) on FarmDetail. .trend-badge CSS.
- Tests: test_farm_history.py (7). Full suite 130 pass; no migration; FE builds.
- Bugs: none.

---
## Section E (enterprise hardening)

### E1 — Harden production settings  ✅ DONE
Decisions (user): DEBUG default False (True via env for dev); SECRET_KEY
fail-fast in prod.
- settings.py: DEBUG defaults False; SECRET_KEY required when DEBUG off (raises
  RuntimeError otherwise, dev fallback key only under DEBUG); ALLOWED_HOSTS
  defaults localhost (env-driven); CORS allow-all only in DEBUG else restricted
  to CORS_ALLOWED_ORIGINS (+ CSRF_TRUSTED_ORIGINS); production SECURE_* block
  (SSL redirect, secure cookies, HSTS, nosniff, X-Frame DENY, proxy SSL header)
  gated on not-DEBUG with a DISABLE_HTTPS escape hatch.
- backend/.env.example documents every var; .env gitignored.
- pytest.ini sets test env (SECRET_KEY+DEBUG) via pytest-env (added to
  requirements-dev) so the hardened settings load under test.
- docker-compose already passed SECRET_KEY/DEBUG=False/ALLOWED_HOSTS;
  added CORS_ALLOWED_ORIGINS. README security section added.
- Verified: fail-fast raises without key (prod), boots with key, dev zero-config.
  Full suite 130 pass. (Settings-only; no migration, no FE change.)
- Bugs: none.

### E2 — Secrets audit + create_admin fix  ✅ DONE
- Audit: no real secrets committed (only the DEBUG-only dev fallback key from
  E1). Rewrote core/management/commands/create_admin.py: password from
  --password or ADMIN_PASSWORD env, REQUIRED (no insecure default), validated,
  never echoed. (Env-sourced secrets + .env.example were delivered in E1.)

### E3 — Password policy + login lockout  ✅ DONE
- AUTH_PASSWORD_VALIDATORS (similarity, min-length 8, common, numeric) in
  settings; enforced via a shared _password_error() helper at ALL set points:
  initial_setup, change_password, admin create-user, admin reset-password.
- Login brute-force protection: DRF ScopedRateThrottle, scope 'login' at
  10/min, wired on login_view (login_view.cls.throttle_scope).
- Tests: test_auth_security.py (7: weak/common/numeric rejected at 3 set
  points, strong accepted, 429 after login limit). conftest autouse fixture
  clears the cache between tests so throttle state doesn't leak across the
  many auth_admin logins.
- Full suite 137 pass. Backend-only; no migration, no FE change.
- Bugs found & fixed (both mine, caught by tests): throttle_scope must be set
  on login_view.cls (not in the body); throttle cache leaked across tests
  until the clear fixture was added.

### E4 — Audit log on money records  ✅ DONE
- core.AuditLog (append-only): timestamp, actor FK + actor_username (survives
  user deletion), action, model, object_id, object_repr, changes JSON
  (update = {field:[before,after]}; create/delete = full snapshot). Migration 0025.
- core/audit.py: pre_save/post_save/post_delete signal handlers on Farm, Flock,
  Sale, DailyEntry, Medication, FeedOrder, FeedTransfer, Bill, BillConfig,
  Document (FeedRate etc. deliberately excluded). Decimal/date/FK/file made
  JSON-safe; no-op saves record nothing. Wired in CoreConfig.ready().
- core/middleware.CurrentUserMiddleware: thread-local request so signals can
  resolve the actor. DRF's JWT auth sets request.user during the view (before
  save signals fire), so API changes capture the JWT user — verified by test.
- Read-only admin-only API /api/audit-log/ (filters: model, object_id, actor,
  action, limit). Read-only Django admin registration.
- Tests: test_audit.py (12). Full suite 149 pass.
- Bugs: none.

### E11 — CI pipeline  ✅ DONE
- .github/workflows/ci.yml: on push/PR to main + release/feeds-only.
  backend job: Postgres 16 service, pip cache, manage.py check,
  makemigrations --check, pytest. frontend job: node 22, npm ci, vite build.
- Verified the whole suite locally against a real Postgres 16 before pushing:
  149 pass on the production DB engine (first time run on Postgres; engine-
  agnostic, no fixes needed).
- README: CI badge + section.

### E6 + E8 — Logging & health endpoint  ✅ DONE
- settings.LOGGING: console handler always; in prod (DEBUG=False) a
  RotatingFileHandler at $LOG_DIR/app.log (default backend/logs/, 10MB x 5).
  LOG_LEVEL env (default INFO prod / DEBUG dev); django.request at WARNING;
  SQL logging opt-in via SQL_LOG_LEVEL. backend/logs/ gitignored.
- GET /api/health/ (core/views/health.py): unauthenticated, unthrottled,
  checks DB (SELECT 1) → {"status":"ok","db":"ok"} 200, or 503 "degraded".
  SECURE_REDIRECT_EXEMPT = ['^api/health/$'] so load balancers can probe over
  plain http in prod while everything else still 301s to https.
- docker-compose: backend healthcheck hits /api/health/ (30s interval,
  40s start_period).
- Verified in prod mode (DEBUG=False): manage.py check clean, app.log created,
  /api/health/ → 200 over http, /api/farms/ → 301 https.
- Tests: test_health_logging.py (7). Full suite 156 pass.
- Bugs: none in code. One test-setup slip: smoke test curled 127.0.0.1 with
  ALLOWED_HOSTS=localhost → 400 (DisallowedHost, correctly logged to app.log).

### E10 — Pin dependencies  ✅ DONE
- backend/requirements.txt pinned to exact versions; gunicorn + psycopg2-binary
  moved into it (Dockerfile no longer installs them ad hoc). requirements-dev.txt
  pinned and now includes -r requirements.txt.
- Finding: Dockerfile is python:3.11-slim, so prod could never get Django 6.x
  (needs 3.12+) and had been silently resolving to Django 5.2 while the dev
  venv ran 6.1 — exactly the drift pinning prevents. Pinned to Django 5.2.19
  (LTS, supported to Apr 2028), i.e. what production actually runs.
- Verified: fresh venv from the pinned files; main 156 pass, release 186 pass,
  manage.py check clean; also green with DeprecationWarning-as-error.
- Bugs: none.

### E5 — Bill immutability + reopen trail  ✅ DONE
- core/billlock.py: once a flock has a Bill, the Bill, the Flock and every
  settlement input (DailyEntry, Sale, Medication, FeedOrder, FeedTransfer —
  incl. rows being moved OFF a billed flock) are locked via pre_save/pre_delete
  signals → BillLocked (HTTP 409). Holds for API, admin and shell. Deleting a
  farm/flock with a bill or bill history is blocked (money trail).
  QuerySet.update() bypasses signals by design (documented).
- Reopen: POST /api/flocks/<id>/reopen-bill/ — admin only, reason ≥10 chars.
  Archives the bill as BillVersion (full JSON snapshot, net/amount paid,
  reopened_by/at, reason), deletes the live bill and sets the flock active.
  Re-closing generates the next version (Bill.version). BillVersion rows are
  permanent. GET /api/flocks/<id>/bill-history/ lists versions + current.
  Reopen is logged (WARNING) and audited (Bill delete + BillVersion create).
- Bill admin is read-only. Migration 0026_bill_lock_versions.
- UI (BillView): 🔒 Locked · Revision N badge, "Revision N" on the printed
  bill, admin Reopen panel with reason, bill-history table.
- Tests: test_bill_lock.py (24). Full suite 180 pass (SQLite + Postgres 16).
  Frontend build clean; bill page checked in a browser.
- Bugs (caught by tests, fixed): API posting an entry to a billed flock showed
  the unrelated "mortality exceeds live birds" error instead of "locked" →
  views now check the lock first (assert_flock_unlocked). Test-only: deletes
  raise inside Django's atomic(savepoint=False), poisoning the test
  transaction → assertions run under a savepoint (prod is autocommit).

### E7 — Error monitoring (Sentry)  ✅ DONE
- config/monitoring.py: Sentry initialised from settings only when SENTRY_DSN
  is set (dev/tests/CI send nothing). SENTRY_ENVIRONMENT (default production /
  development), SENTRY_RELEASE, SENTRY_TRACES_SAMPLE_RATE (default 0, clamped,
  junk-safe). Unhandled exceptions + ERROR logs → events; WARNING → breadcrumbs.
- Privacy for a system holding PAN/bank data: send_default_pii=False,
  max_request_body_size='never', EventScrubber with extra denylist (pan, gstin,
  aadhaar, account, ifsc, upi, phone, tokens...). Business numbers kept.
- `manage.py check_monitoring` sends a test event to confirm wiring.
- sentry-sdk==2.75.0 pinned; docker-compose passes SENTRY_* to backend;
  .env.example + deploy/setup.sh document SENTRY_DSN.
- Tests: test_monitoring.py (18) incl. end-to-end with the real SDK and a
  capturing transport: a forced 500 on /api/auth/login/ is reported with
  endpoint + release while the password/PAN in the body never appear.
  Full suite 198 pass. Prod-mode boot with a DSN verified.
- Bugs: none in code (test fixes only: scrubbed values are AnnotatedValue
  placeholders until serialisation; event carries `transaction`, not url).
- Frontend error capture deferred to E12 (error boundary).

### E9 — Automated, verified backups  ✅ DONE
- Findings in the old setup: backup.sh was never scheduled (setup.sh installed
  no cron/timer); uploaded documents (media volume) were not backed up at all;
  restore.sh piped a plain dump into the live DB without dropping first
  (restore over existing data would error/duplicate); paths hard-coded; no
  integrity check.
- deploy/backup.sh (rewrite): pg_dump --clean --if-exists → gzip, verified
  (gzip -t + pg_dump completion marker) before it counts, .partial→rename,
  sha256 per file; documents archived from the backend media volume; flock so
  runs never overlap; retention RETENTION_DAYS (30) but always keeps newest
  MIN_KEEP (7); off-box copy via rclone BACKUP_REMOTE (+ remote pruning; old
  onedrive: remote still auto-used); last_backup.json status; healthchecks.io
  style ping (…/fail on failure) so a backup that fails OR never runs alerts.
- deploy/restore.sh (rewrite): `latest` or a file; refuses a checksum
  mismatch before touching anything; pre-restore safety dump; stops backend;
  restores in ONE transaction (error → rolled back); restarts backend; then
  restores documents from the same run. --no-media, --yes.
- deploy/verify-backup.sh: weekly restore test into a throw-away postgres:16
  container; checks django_migrations/users and reports core table counts;
  last_verify.json + its own ping URL.
- systemd timers (daily 02:30 IST, weekly Sun 04:00 IST, Persistent=true so a
  missed run happens at next boot); deploy/install-backups.sh (idempotent,
  creates /etc/poultrytrack/backup.env from backup.env.example, retires any
  old cron entry); setup.sh runs it. Runbook docs/BACKUPS.md; README section.
- Tests: test_backup_scripts.py (18) run the real scripts against real
  PostgreSQL DBs (skip when no Postgres/pg tools; run in CI's postgres job).
  Also round-tripped the full migrated app schema (113 FKs) incl. restoring
  over a damaged live DB; shellcheck clean at warning level.
- BUG-005 (found while wiring setup.sh, fixed): setup.sh still called
  create_admin with no password and printed "admin / admin123". Since E2
  create_admin requires a password, so a fresh server got NO admin and a
  login that didn't exist (failure masked as "Admin already exists"). Now a
  random strong password is generated, passed via ADMIN_PASSWORD and shown once.

### E12 — Error boundary + frontend tests  ✅ DONE
- components/ErrorBoundary.jsx: wraps the routed page area (resetKey = path,
  so navigating away recovers) — a crashing screen shows "Something went wrong
  on this page" with Try again / Go to dashboard / Reload while the navbar keeps
  working; a top-level full-page boundary in main.jsx catches the rest.
- utils/errorReporting.js: crashes, window errors and unhandled promise
  rejections are POSTed to /api/client-errors/ (fetch, not axios; dedupe 1/min
  per message, max 10 per page load, path only — no query strings, size caps,
  never throws). Axios HTTP errors are left to the screens.
- Backend /api/client-errors/ (AllowAny, throttled 30/min/IP, size-capped)
  logs at ERROR on core.client_errors → app.log and Sentry (E7) with no new
  frontend dependency.
- Vitest 5 + Testing Library + jsdom (pinned); `npm test`. 14 frontend tests
  incl. an App-level test proving a crashing page leaves the navbar usable.
  8 backend tests (test_client_errors.py). CI frontend job now runs npm test.
- CI FIX (found on the first real CI run of main, which failed): ubuntu-latest
  moved to Ubuntu 26 with a newer PostgreSQL client than the postgres:16
  service; pg_dump 17+ dumps don't restore into 16 → backup-script tests
  failed in CI only (pass locally with pinned deps on PG16). CI now installs
  postgresql-client-16; the tests skip with a clear reason on a client/server
  major mismatch; pytest-github-actions-annotate-failures surfaces failing
  tests as annotations (readable via the API — job logs aren't).
- Note: pre-existing ESLint debt (43 errors in older files) left as is; all new
  files lint clean. Suite: backend 224, frontend 14.

### E15 — Silent token refresh  ✅ DONE
- Finding: there was NO refresh endpoint — the stored refresh token was never
  used, so every user was hard-logged-out exactly 24 h after login (mid-entry,
  unsaved form lost).
- Backend: POST /api/auth/token/refresh/ (throttled 60/min/IP; returns 401 —
  never 500 — for expired/blacklisted/malformed tokens or deleted/inactive
  users; simplejwt's own serializer 500s on a deleted user). Access tokens now
  30 min (JWT_ACCESS_MINUTES), refresh 7 days (JWT_REFRESH_DAYS), rotated on
  every use with the old one blacklisted (token_blacklist app) → sliding
  session: active users stay signed in, 7 days idle → sign in again.
  POST /api/auth/logout/ revokes the refresh token (idempotent, works with an
  expired access token). Admin password reset signs that user out everywhere.
  flushexpiredtokens runs on container start.
- Frontend (api/client.js): on 401 → one shared refresh (single-flight;
  Web Lock across tabs; reuses a token another tab already refreshed, since
  rotation revokes the old refresh) → replay the request. Auth endpoints and
  already-retried requests never refresh (no loops). Dead refresh → session
  cleared → /login?expired=1 with "Your session expired" notice. Logout calls
  the revoke endpoint.
- BUG-006 (fixed): change-password returned only a message but the page
  stored res.data.access/refresh → "undefined" tokens → user kicked out right
  after changing their password. Now returns fresh tokens and revokes all
  other sessions ("signed out on other devices"); page min length 6 → 8 to
  match the server policy.
- Tests: backend 17 (test_token_refresh.py), frontend 8 (tokenRefresh.test.js,
  real interceptors over a fake adapter). Browser E2E: stale access → 4
  concurrent 401s → exactly one refresh → page loads; revoked session →
  /login?expired=1 with notice. Suite: backend 241, frontend 22.

### E13 — API pagination + throttling  ✅ DONE
- Constraint: every screen (Feeds, Chicken, Layer) expects plain JSON arrays;
  turning DRF pagination on globally would break them all.
- core/pagination.py OptionalPageNumberPagination (project default): plain
  list unless ?page= / ?page_size= is given → {count,next,previous,results};
  page_size 50, capped at 500; unordered querysets ordered by pk for stable
  pages. Verified no existing frontend/backend code sends page params.
- GuardedListMixin on the high-volume lists (daily-entries, sales,
  medications, flocks): a list with no ?flock= (flocks: ?farm=/?status=) is
  always paged, so an unfiltered "everything ever" request can't run away.
  Screens always filter, so they're unaffected. Flocks list gained ?farm= and
  ?status= filters and a stable order. (Unfiltered /api/flocks/ previously
  returned every flock; nothing in the UI calls it.)
- Throttling: UserRateThrottle 600/min per user + AnonRateThrottle 60/min per
  IP on top of the scoped ones (login, client errors, token refresh);
  env-configurable (THROTTLE_USER_RATE / THROTTLE_ANON_RATE). Health check stays
  exempt.
- Tests: test_pagination_throttle.py (18) — shapes unchanged for every screen
  endpoint, paging correctness (no gaps/dupes), cap, guard, per-user isolation,
  anon limit, health exempt. One older test updated to use ?farm= (it relied
  on the unfiltered flocks list). Suite 259.

### E14 — Soft delete + Recycle Bin  ✅ DONE
- core/softdelete.py: Farm, Flock, DailyEntry, Sale, Medication, FeedOrder,
  FeedTransfer, Document are never destroyed by a delete — stamped
  deleted_at / deleted_by / deletion_batch and hidden by the default manager
  and every reverse relation (so totals, bills, dashboards and reports ignore
  them automatically); `all_objects` sees everything. QuerySet.delete() (incl.
  Django admin bulk delete) is soft too; hard_delete() exists for future purge.
  Actor comes from the request (E4 middleware).
- Soft cascades: farm → flocks, feed orders, documents; flock → entries,
  sales, medications, documents. One delete action = one batch; restore brings
  back exactly that batch (items deleted separately earlier stay deleted).
- Money trail (E5): a flock with a bill or bill history, or a farm owning one,
  can't be deleted (409 with a clear reason); records under a billed flock stay
  locked (delete and restore).
- Uniqueness is now among LIVE rows: farm_code and (flock, date) daily entry
  are partial unique constraints, so a deleted farm's code / a deleted day can
  be re-entered. Restore refuses with a clear message if it would clash, or if
  the parent is still deleted ("restore that first").
- Admin Recycle Bin: GET /api/trash/ (one row per delete action, with what was
  removed alongside it and who did it), POST /api/trash/<batch>/restore/
  (all-or-nothing). New Recycle Bin page + nav link (admin); delete prompts
  now say an admin can restore. Audit log records soft delete as `delete` and
  restores as a new `restore` action. Uploaded files are kept on delete.
- Migration 0027 verified on a database with existing data (rows kept, live
  duplicates still blocked by the DB, deleted code reusable).
- BUG-007 (caught by the new tests, fixed before commit): after moving
  farm_code to a live-only constraint, DRF no longer validated it, so a
  duplicate live code returned 500 → explicit serializer validation (400);
  same for duplicate daily entries. Also: the Recycle Bin fired a forbidden
  request for non-admins before redirecting; "4 daily entrys" pluralisation.
- Tests: backend 20 (test_soft_delete.py), frontend 5 (RecycleBin.test.jsx);
  browser E2E delete → bin → restore. Suites: backend 279 (Postgres + SQLite),
  frontend 27.

### Local production deploy kit  ✅ DONE
- docker-compose.local.yml (override: nginx on :8080 only, local nginx conf, no
  Let's Encrypt mount, DISABLE_HTTPS, localhost hosts/origins) +
  deploy/nginx.local.conf + deploy/local.sh (up/status/logs/down/reset;
  generates a git-ignored .env.local with random secrets; waits for health).
- Production fixes found while preparing it:
  - BUG-008: backend Dockerfile ran collectstatic at BUILD time with no
    SECRET_KEY; since E1 that raises and `|| true` hid it → new images ship the
    Django admin without CSS. Moved to container start (writes the static volume).
  - nginx /admin/ lacked X-Forwarded-Proto → admin redirect loop under the E1
    HTTPS settings. Fixed in deploy/nginx.conf.
  - No .dockerignore: on a Mac, `COPY . .` copies macOS node_modules over the
    image's Linux ones (frontend build breaks) and venv/db/media into the
    backend image. Added backend/ and frontend/.dockerignore.
  - Frontend image Node 20 (EOL) → 22, matching CI.
  - First-time Setup created an admin WITHOUT Django-admin access (create_admin
    made a superuser) → Setup now makes a superuser too (+1 test).
- Verified: compose merge (`docker compose config`); full production stack
  emulated without Docker (Docker Hub unreachable from the build workspace):
  Python 3.11 + pinned requirements, container start sequence, gunicorn,
  production frontend build, nginx with nginx.local.conf on :8080, Postgres 16.
  Browser walkthrough: fresh DB → Setup → dashboard → create farm → Django
  admin styled + login → Recycle Bin; no page errors, no 5xx; no https
  redirect; security headers present.

### BUG-009 — "Admin creates a supervisor but there's no way to set a password"  ✅ FIXED
- Reported by Sai. The New User form did have a Password field, but browsers
  treat a username + password pair as a LOGIN form and silently autofill the
  ADMIN's own saved credentials into it — so the field looked already filled
  (no visible way to set one), and creating the user could quietly give the
  supervisor the admin's password. The admin then had no way to know or hand
  over the supervisor's password, no visible reset, and nothing made the
  supervisor replace a password someone else chose.
- Fix (User Management): autocomplete off/new-password so the browser never
  injects the admin's login; Show/Hide + Generate (strong, readable, e.g.
  Kp7m-Qx4t-Rw9a); policy hint; after Create, a "Share these login details"
  card (username + password, Copy, shown once); per-user "Reset password"
  (new temporary password, signs them out, shown once); "temporary password"
  marker in the list; server error messages shown properly.
- Temporary passwords: UserProfile.must_change_password (migration 0028) set
  when an admin creates a user or resets a password. The supervisor logs in
  with it, is taken to "Set your password" (welcome message) and can't reach
  anything else — enforced by the server too (JWT auth returns 403
  password_change_required except /auth/me, change-password, logout). Choosing
  the same password again is refused. First-time Setup admin is not forced.
- Tests: backend 9 (test_user_passwords.py), frontend 11 (UserManagement,
  ChangePassword, password generator). Browser E2E: admin Generate → card shows
  password → supervisor logs in on a phone-size screen → forced to set own →
  dashboard → re-login with own password; temp password then rejected (401).
  Suites: backend 289, frontend 38.

### Owner View / Break-even / Feed Forecast → admin only  ✅ DONE
- Requested by Sai: these business-sensitive screens (owner P&L and grower
  leaderboard, break-even per flock, feed demand) were visible to every
  non-plant user, supervisors included.
- Backend: /api/reports/owner-dashboard/, /break-even/, /feed-forecast/ now
  require an admin (IsAdmin) → 403 for supervisor/plant, 401 anonymous — so the
  data can't be fetched by URL or API either.
- Frontend: nav links shown to admins only; AdminRoute sends anyone else who
  opens the URL to their dashboard. Supervisors keep Today, Farms, Feed, Reports.
- Tests: backend 13 (test_admin_only_reports.py), frontend 5. Suites: backend
  302, frontend 43.

### Access audit + fixes (BUG-010 … BUG-016)  ✅ DONE
Requested by Sai after BUG-009 / Owner View: "check for other similar bugs".
Method: an access matrix — every API endpoint called as admin, as a Zone-A
supervisor against Zone-A and Zone-B records, as the feed-mill (plant) user
and anonymously; plus reading the views. Policy agreed with Sai: supervisors
see and edit only their regions (incl. their own farms' bills); billing
settings admin-only; plant user = feed only.
- BUG-010 (write): anyone logged in could create a FLOCK on ANY farm —
  supervisors in other regions and the feed-mill user (CanEditFlock skipped
  the farm check on create).
- BUG-011 (write): the plant user could create FARMS (any region); a
  supervisor with no regions could create farms anywhere.
- BUG-012 (write): FEED ORDERS — anyone could create orders for any farm, and
  supervisors / the mill could edit or delete any order, incl. other regions'
  and already-dispatched ones. Now: farm's supervisor or admin; edits/deletes
  only while pending (admin any time); the mill only marks sent; an order's
  flock must belong to its farm.
- BUG-013 (write): FEED TRANSFERS — anyone could move feed out of another
  region's farm/flock. Now both farms must be the user's (admin: any); flocks
  must belong to the chosen farms.
- BUG-014 (read): every logged-in user could read every region's farms,
  flocks, daily data, feed, dashboard, cumulative/performance history,
  monthly/region/till-date reports, exports and BILLS. Now one rule
  (core/access.py visible_farms) scopes all of them; other-region records
  return 404. Billing settings (GET too) admin-only.
- BUG-015 (read): the plant user (Feed screen only) could read everything via
  the API. Now NotPlant blocks flocks, daily data, dashboard, reports, bills;
  their farm list is names only (no PAN/grower data); frontend sends them to
  /feed from any other URL.
- BUG-016: flock/farm cumulative and flock export crashed with 500 on an
  unknown id (bare .get) → 404. close-and-bill returned an existing bill
  before checking permission → now checked first.
- Also: the farm form derived a supervisor's regions only from farms already
  assigned, so a newly assigned (empty) region couldn't be chosen → uses
  assigned_regions too.
- Tests: test_access_matrix.py (71: 37 read checks × 4 roles, 19 write checks
  × 3 roles, list-content checks, own-region work still allowed). Suite 373.

### Browser test suite + more bugs it found (BUG-017 … BUG-020)  ✅ DONE
- Playwright suite in frontend/e2e (84 tests, ~3 min, CI job "e2e"): real
  production build + real API on a throwaway SQLite DB seeded by
  `manage.py seed_e2e` (refuses to run unless DEBUG=True and E2E_SEED=1 — it
  wipes the database). Specs: auth (login per role, wrong password, logout,
  silent refresh, revoked session, first-login password), roles (menus, every
  restricted URL per role), regions (lists, dashboard, direct links → not
  found, feed page, dropdowns, reports), flock (entries incl. duplicate /
  out-of-range / negative / high-mortality confirm OK+Cancel / over-mortality /
  over-stock, edit, delete, sale incl. over-sale, medicine, export), billing
  (close → bill → lock on screen and API → admin reopen with reason →
  revision 2 + history), farms (create, duplicate code, supervisor regions,
  edit, new flock), feed (order → mill sends → supervisor receives, dispatched
  lock, cancel, transfer, rates), users (generate → first login → reset →
  delete), Recycle Bin (entry + whole farm restore, billed farm refused),
  reports (all tabs, exports, admin reports, no page errors), phone (menu,
  daily entry, no sideways scroll).
- Settings: SQLITE_PATH (separate test DB) and THROTTLE_LOGIN_RATE env
  (production default 10/min unchanged).
- BUG-017 (main only): Chicken Center, Layer Farm, accounting and inventory
  APIs only required a login — a Feeds supervisor or the feed mill could read
  and change another business's sales, payments, P&L and balance sheet. Now
  admin-only (one check in core/authentication.py); "Switch Business" and the
  business switcher shown to admins only; others go straight to Feeds.
- BUG-018: opening another region's / a deleted farm showed a blank page
  forever; a flock showed raw "No Flock matches the given query." → clear
  "not found" messages with a way back. FarmDetail no longer calls the
  admin-only user list for supervisors.
- BUG-019: "Update Rate" for a week that already had a rate (e.g. correcting
  this Monday's rate) failed with raw JSON {"non_field_errors": …}. Saving
  now corrects that week's rate.
- BUG-020: several screens showed raw JSON or a generic "Failed" instead of
  the server's reason (farm form, feed order / transfer / rate forms, feed
  actions, closing a flock, setup, document upload) → readable messages.
- Noted, not changed: with all admin links the desktop menu wraps to two lines
  at 1280px wide (cosmetic).

### Status recheck: early-morning date bug + library security updates (BUG-021, BUG-022)  ✅ DONE
- BUG-021: every date field took "today" from `toISOString()`, which is the
  UTC date. Between midnight and 5:30 AM India time that is still yesterday,
  so a supervisor entering data early in the morning got yesterday as the
  default and could not pick today (max = yesterday); Chicken/Layer reports
  also started the month on the last day of the previous month. All 18
  screens now use `utils/dates.js` (local date). The server was already
  correct (Django runs on Asia/Kolkata).
  The browser tests had the same flaw (their "today" was UTC while the server's
  is IST → random failures 6 PM–midnight UTC, e.g. on CI); helpers now use the
  India date and the test browser runs in Asia/Kolkata like real users.
  Tests: utils/dates.test.js (1:30 AM and 1 Dec 2 AM cases), e2e
  early-morning.spec.js (browser clock at 1 AM IST).
- BUG-022: `npm audit` reported 5 vulnerable libraries (axios, react-router,
  follow-redirects, form-data — 4 high). Updated within the same major
  versions (lockfile only): axios 1.21.1, react-router 7.18.6. 0 left.
  Backend `pip-audit`: no known vulnerabilities.
- Found, not changed yet (next work item E20): the dashboard runs ~50 database
  queries per farm (3 farms → 166, 18 → 929); farm list ~41/farm, flock list
  ~38/flock, owner view ~23/farm. Fine today, slow at 100+ farms.

### Feed leakage detector (Insights #1)  ✅ DONE
- Supervisors record a physical **bag count** (BPSC/BSC/BFP) on the flock page
  ("Feed Bag Counts" → "+ Bag Count"); the app shows paper stock vs counted and
  the difference right away. One count per flock per day; only an admin can
  change or remove a count (it is evidence); counts lock with the bill; audited.
- Paper stock at a date = delivered + transferred in − transferred out −
  recorded as eaten, up to that date (core/feed_audit.py).
- Admin **Insights → Feed Audit** (/feed-audit): active flocks + flocks closed in
  the last 45 days, worst first, with feed value at risk (BillConfig feed ₹/kg):
  - Bags short: count below paper by ≥ 2 bags and ≥ 2% of feed received (high)
  - Bags extra: count above paper — feeding recorded that didn't happen (medium)
  - Above standard: recorded feed > 10% over the Cobb intake standard for the
    birds' ages and numbers while weight < 95% of standard (high) or not
    weighed (medium)
  - Left at close: paper stock left on a closed flock, never moved (high)
  - Count due: no count in 7 days, flocks 7+ days old (low)
  The report loads everything in a fixed number of queries (test proves it
  doesn't grow with the number of flocks).
- Menu: Feed Forecast / Owner View / Break-even moved into one **Insights** page
  (admin), which also fixes the admin menu wrapping at 1280px and leaves room
  for the next insight pages.
- Tests: backend test_feed_audit.py (24), vitest Insights/Feed Audit access,
  e2e feed-audit.spec.js (count → short → audit → filter → admin removes).

### Heat-stress forecast (Insights #2)  ✅ DONE
- Admin sets **one map point per region** (type it, or "Use my location") on
  the Heat Stress page → Region locations. Regions without a point are listed,
  never guessed.
- Weather: Open-Meteo hourly forecast (free, no key), 5 days, cached 2 hours
  per region; an outage shows a message, not an error. The production server
  needs outbound internet to api.open-meteo.com.
- Risk: livestock heat index THI = 0.8·T + RH/100·(T − 14.4) + 46.4 at the
  hottest hour → OK < 74 · Watch 74–78 · Danger 79–83 · Emergency ≥ 84; then
  birds 28+ days one level up, chicks under 14 days two down, EC shed one down
  — using the birds' age on each forecast day.
- **Heat Stress page** (/heat-stress): weather by region, every active farm ×
  5 days, and what to do at each level. Admin: all farms (Insights card);
  supervisor: their regions, reached from a **dashboard heat alert** shown when
  any of their farms is at Danger or worse in the next 3 days.
- WEATHER_FAKE=1 gives a fixed hot week (used by the browser tests).
- Tests: backend test_heat.py (29, incl. Open-Meteo parsing + cache, outage,
  region scoping, bad coordinates), vitest HeatBanner (3), e2e heat.spec.js (4).

### Chick quality by hatchery (Insights #3)  ✅ DONE
- Flock gets **hatchery** (from an admin-kept list), **dead on arrival** and
  **average chick weight**. Recorded in the "Place New Flock" form and editable
  on the flock page ("Chicks:" bar → Edit) while the flock is active. DOA is
  for hatchery quality only — not deducted from chicks placed, not in the bill.
  Checks: DOA ≤ chicks, chick weight 20–80 g, retired hatchery can't be picked
  for a new flock (old flocks keep theirs).
- Hatchery list: everyone except the feed mill can read it; only an admin adds,
  retires ("not used") or removes one; one with flocks can't be removed.
- Admin **Insights → Chick Quality** (/hatcheries): per hatchery for flocks
  placed in the last 90/180/365/730 days — first-week mortality (days 1–7,
  only flocks past week 1; Recycle-Bin entries excluded), flocks over the
  BillConfig first-week limit, DOA %, average chick weight, final mortality of
  closed flocks; verdict: above limit (high) / ≥ 0.5 pt worse than average
  (warning) / OK; click a hatchery for its flocks. "Not recorded" grouped last.
- Tests: backend test_hatchery.py (15), e2e hatchery.spec.js (5).

### Best day to lift (Insights #4)  ✅ DONE
- Admin enters the day's **market rate** (₹/kg live bird) on the Lift Planner
  page; saving a date again corrects it (20–500, not in the future). If none in
  the last 7 days the planner uses the weight-weighted rate of our own sales in
  the last 7 days; if neither exists it asks for today's rate.
- **Insights → Best Day to Lift** (/lift-planner, admin): every active flock
  aged 28–56 days, value of lifting today vs each of the next 10 days =
  birds left × projected weight × (price − grower charge/kg) − feed eaten
  meanwhile. Weight: last weighing carried on the Cobb curve at the same % of
  standard (standard if never weighed). Deaths: the flock's last 7 days (the
  standard rate otherwise). Feed: standard intake × birds at the latest BFP
  feed rate (or BillConfig). Price: flat, or "follow the trend" = half the
  recent 14-day change, capped at ±₹1.5/kg/day. Shows best day, extra ₹ vs
  lifting today, advice, and a day-by-day table.
- Sanity check (10,000 standard birds, flat price): ₹90 → lift now; ₹110 → a
  30-day flock is best around day 38; ₹130 → hold to the end of the window.
- Tests: backend test_lift.py (17), vitest access, e2e lift.spec.js (5).

### Page speed (E20)  ✅ DONE
- Cause: every flock figure (live birds, mortality, feed used, sales, medicine
  cost, feed stock, weight vs standard, water alerts, …) ran its own query, and
  pages computed 20–40 of them per flock, flock by flock.
- Fix: `core/prime.py` — `prime_flocks(flocks)` loads those totals for all
  listed flocks in ~8 grouped queries and stores them on each instance; the
  figures read from memory when primed. Un-primed flocks behave exactly as
  before (fresh queries), and serializers prime → serialize → unprime, so
  nothing ever shows stale totals after a save. Farm lists fetch all farms'
  flocks and supervisors at once; Dashboard, Owner View, Till-date, Feed
  Forecast, Break-even and Feed Stock load per-farm totals in grouped queries.
- Database queries per page (2 farms → 12 farms), before → after:
  Dashboard 115→623 ⇒ 34→32 · Farms 85→495 ⇒ 13→13 · Flocks 81→461 ⇒ 13→13 ·
  Owner View 51→281 ⇒ 13→13 · Till-date 26→116 ⇒ 16→16 · Feed Stock 14→64 ⇒
  9→9 · Feed orders 8→28 ⇒ 4→4 · Feed Forecast 10→40 ⇒ 12→12 · Break-even
  12→52 ⇒ 12→12.
- Proof nothing changed: the old and new code produced byte-identical JSON
  (timestamps aside) for 15 pages on the same messy dataset (deleted entry,
  transfers, pending orders, closed + billed flock, unpriced sale).
- Tests: test_page_speed.py — query count must not grow from 2 to 12 farms on
  10 pages; every primed figure equals its un-primed value (incl. a flock with
  no data, a Recycle-Bin entry, a closed billed flock); primed figures need 0
  queries; a saved entry shows up at once on detail and list.

### Settings → Features: switch Feed Audit and Best Day to Lift on/off  ✅ DONE
- New admin **Settings** page (user menu, top right → Settings). "Features"
  lists each switchable feature with what it does and what turning it off
  does, an on/off switch, and who changed it last.
- Switchable now: **Feed Audit (bag counts)** and **Best Day to Lift**. Both
  start on. Adding another feature = one entry in `core/features.py`.
- Off means: screens hidden for everyone (Insights card, the page shows "turned
  off" with a link to Settings for the admin, bag counts gone from the flock
  page) and the API refuses (403 "… is turned off. An admin can turn it on in
  Settings → Features."). Data already saved (bag counts, market rates) is
  kept and comes back when switched on. Every switch is in the audit log.
- BUG-023 (browser tests): switching user inside one test could leave the
  previous user in browser storage (their page was still loading and wrote it
  back), so the admin was briefly treated as a supervisor and redirected →
  random failures. `loginAs` now clears storage first (32/32 repeated runs).
- Tests: backend test_features.py (7), vitest Settings.test.jsx (3), e2e
  settings.spec.js (4).

### Who gets the next chicks — grower ranking + placement plan (admin only)  ✅ DONE
- **Insights → Who Gets the Next Chicks** (/grower-ranking), admin only, with
  its own on/off switch in Settings → Features (starts on).
- Score 0–100 per farm from its last 4 settled (billed) flocks in 2 years,
  using the bill's final numbers: FCR 45%, mortality 35%, consistency (spread
  of FCR between cycles; one cycle = middle) 20%. Each part is a percentile
  among your scored growers (best = 100). Farms with no settled flock are
  listed separately as new growers. Click a grower for its cycles.
- Availability: a farm can take chicks when it has no running flock, its last
  flock is billed, and it was settled at least N rest days ago (default 14).
- Plan: enter chicks available (+ rest days, region) → free farms filled in
  score order, then new growers; each gets its capacity, or the chicks left
  when that is within the ±5% capacity rule, else it is skipped; chicks that
  fit nowhere are shown as left over.
- Tests: backend test_placement.py (11), vitest access, e2e
  grower-ranking.spec.js (4).

### System Health page (admin, E16)  ✅ DONE
- **Settings → System Health →** (/system-health), admin only. Overall
  status, then a card per check (✓ / ! / ✕ / i):
  - Database: answering + size.
  - Backups: last nightly backup from deploy/backup.sh's last_backup.json —
    OK ≤ 26 h, "needs a look" ≤ 50 h, "needs action" if older or FAILED;
    "not set up on this computer" on the Mac. docker-compose.yml now mounts
    ${BACKUP_DIR:-/root/backups} read-only into the backend for this.
  - Errors (24 h): server + screen errors. ERROR logs are now also stored in
    the database (core/error_log.py, newest 500 kept, never breaks a request).
  - Yesterday's daily entries: active flocks missing one, by farm.
  - Weather (Heat Stress): forecast service reachable?
  - Switchable features: which are on/off.
  Then the 20 most recent errors and "Who is active": each user's last
  sign-in, last change and changes in 7 days.
- Sign-in now records "last login" (wasn't recorded before).
- Tests: backend test_system_health.py (15), vitest access, e2e
  system-health.spec.js (3).

### Access audit #2 + company costs / PAN admin-only (BUG-024 … BUG-026)  ✅ DONE
- Probed every API endpoint (185 on main, 99 on release) as admin, Zone-A
  supervisor, feed-mill user and signed out (reads), plus a POST to every list
  endpoint (writes). No other-region data, nothing for signed-out users,
  every admin page / Settings / Insights refused for non-admins, and writes
  limited to each role's own work. Decided with Sai:
- BUG-024 Supervisors saw company costs → now hidden for everyone but the
  admin, from every API response in one place (core/redaction.py middleware):
  bill production cost + chick/feed/medicine/admin cost + avg selling price +
  config snapshot; feed prices, total feed cost, total sale amount and cost
  per kg in dashboard/reports/farm history; Cost/Kg column in the monthly
  Excel. Kept: the grower's payment (growing charges, incentive, recoveries,
  TDS, net payable), birds/feed/weights/FCR, their own sale rates and
  medicine costs. The Feed rates list is refused for supervisors (admin and
  the feed mill keep it). Screens hide those columns/cards instead of showing
  blanks; Feed Stock no longer loads prices for supervisors (it would have
  broken the page).
- BUG-025 Grower PAN visible to supervisors → admin only (screens + API);
  "has a valid PAN" yes/no kept.
- BUG-026 A supervisor saving a farm sent PAN too → now ignored for
  non-admins, so they can't change or clear it.
- Kept as is (Sai's call): region names list visible to supervisors.
- Tests: backend test_company_costs.py (7, incl. "no hidden field anywhere in
  15 supervisor pages"), access matrix updated, e2e company-costs.spec.js (4).

### UI redesign 1/3 — Style B foundation: sidebar app frame + design system (+ BUG-027)  ✅ DONE
- Sai picked Style B ("control room") from the mockups.
- New app frame (components/AppShell.jsx, styles/shell.css): navy sidebar
  with grouped navigation (Operations / Analysis / Admin — only what the
  role can use), user menu at the bottom (Settings for admin, Change
  Password, Logout; opens on hover or tap), slim top bar with farm search
  (opens Farms filtered, ?q=) and the alert bell. Phones: the sidebar slides
  in from the menu button. Chicken Center and Layer Farm (main) use the same
  frame with their own groups. Line icons (components/Icon.jsx) replace emoji.
- Design system (styles/theme.css, loaded last): IBM Plex Sans + Plex Mono
  for figures, teal accent (white-label: VITE_BRAND_PRIMARY_COLOR), cool
  grey ground, flat bordered panels, compact tables, status chips
  (.chip-ok/warn/danger/info), .panel/.panel-head. Every existing page picks
  it up; key screens get redesigned next.
- BUG-027: "Water:feed ratio low" was shown on every flock where water
  wasn't recorded (0 L counted as "drank nothing"). Water 0 = not measured:
  no ratio, no alarm.
- Tests: vitest AppShell (4), water test, e2e helpers read the sidebar; all
  browser tests pass on the new frame.

### UI redesign 2/3a — Control-room dashboard (+ BUG-028)  ✅ DONE
- Dashboard rebuilt in Style B: key figures with 14-day trend lines (live
  birds, mortality, daily entries done/due, feed used, feed on farms + pending
  orders; feed rates admin-only), Regions panel, Alerts panel, and a
  "Flocks on the ground" table — age, live, mortality %, weight vs standard,
  feed on farm, last entry and a NEXT ACTION per flock (Close & bill / No
  entry for N days / Daily entry due / Order feed / On track), worst first.
  Empty farms listed under the table. Phones: two figures per row, flocks as
  cards.
- Backend: core/control_room.py adds the figures to /api/dashboard/ from the
  already-primed flocks (no extra per-flock queries).
- Shared UI pieces: components/ui.jsx (StatTile, Sparkline, Panel, Chip,
  Meter), utils/format.js (fmtNum, fmtDate).
- BUG-028: a farm's rest period (Who Gets the Next Chicks) and the owner
  dashboard's "closed in period" took the bill's date from its UTC time, so a
  bill settled between 00:00 and 05:30 IST counted from the day before. Now the
  Indian date. Tests also failed in that window (they worked out "today"
  before Django set the clock to IST); conftest sets IST first.
- Tests: test_control_room (4), e2e dashboard.spec (2); all suites pass.

### UI redesign 2/3b — Farms as a table  ✅ DONE
- Farms page is now one table: farm (name, code, owner, place), region, shed,
  capacity, status chip (Running · day N → opens the flock; Sold out · bill
  due; Empty), live birds, mortality %, batches, supervisors.
- Filters: All / Running / Empty with counts, region (when there is more than
  one), search across code, name, owner, region, place and supervisor. All
  kept in the address (?status=&region=&q=), so the top-bar search and
  bookmarks open the same view. Phones: one card per farm.
- Tests: e2e farms-table.spec (2).

### UI redesign 2/3c — Flock page with tabs  ✅ DONE
- Breadcrumb (Farms / farm / flock placed …), status chip next to the title
  (Active · day N / Sold out · bill due / Closed), actions on the right.
- Tabs, kept in the address (?tab=): Overview · Daily entries · Sales · Feed ·
  Health · Documents, with counts. After saving an entry, sale, medicine or
  feed order the matching tab opens, so the new row is in view.
- Overview: four key figures (live birds, mortality with trend, FCR + EPEF,
  weight vs target), body-weight vs Cobb standard and mortality charts,
  and a side column with the summary, performance score and chick quality.
  Feed tab: flock stock, schedule progress, feed-by-type chart, bag counts.
  Health tab: water warnings and medicines. Charts restyled to the theme.
- No change to forms, saving, billing or permissions.
- Tests: tabs e2e; flock, feed-audit, settings and recycle-bin tests open
  the right tab. 127 browser tests pass.

### Billing rate cards (no code change when rates change)  ✅ DONE
- Asked for: the bill formula was hardcoded; the new Jangaon card (effective
  1 Nov 2026) uses a different growing-charge rule. Make rates a setting.
- Rate cards: BillConfig is now a list of named, dated cards (name, effective
  from, notes). Settings → Billing Rates: add a card (copied from the latest),
  edit, copy, make default, delete (not the default, not one used by a bill).
  A live "check" shows the growing charge at ₹90/93/95/98/102 cost.
- Two growing-charge methods, chosen per card:
  - Standard (new card): standard charge ± % of (standard cost − actual
    cost) — separate up/down %, minimum, optional maximum; same for all
    grades. ₹8.50, ₹95, 50%/50%, min ₹5.50: cost 93 → 9.50, 98 → 7.00,
    102 → 5.50.
  - Margin & grade (old cards): selling price − cost, ± % by grade. Unchanged.
- New card fields: medicine at actual for every farm, standard avg body weight.
- Billing: the card in effect on the flock's placement date is used by
  default; an admin can pick any card in Close & Generate Bill and sees a
  preview (growing charge, incentive, recoveries, net payable, after TDS)
  before anything is saved (/bill-preview/, rolled back). Supervisors always
  get the placement-date card. The bill records its card (rate_card + name,
  method and rule in the snapshot) and shows "Rate card" and the rule.
- Existing card renamed "Original rates" by the migration; old bills unchanged.
- Tests: test_rate_cards (14), e2e rate-cards.spec (3); all suites pass.

### Supervisors cover for each other; regions only for performance  ✅ DONE
- Asked for: any supervisor can view and enter data for any farm (someone covers
  when the responsible supervisor is on leave); regions only for metrics and
  reports; keep a log of who entered a farm's figures each day.
- Access (core/access.py): supervisors see every farm; UserProfile.can_edit_farm
  is true for any supervisor (entries, sales, medicines, feed orders/transfers,
  bag counts, documents, new flocks, close & bill). A farm's own details and
  deleting it stay with its region's supervisor (can_manage_farm) or admin.
  Admin-only items (company costs, PAN, billing rates, users…) unchanged.
- Regions = performance scope: dashboard, reports (monthly + Excel, region,
  till date) and the heat warning open on the supervisor's regions; a
  "My regions / All farms" switch (?scope=all) shows everything. Admins have
  no switch (always all). The alert bell follows the dashboard default.
- Who entered: DailyEntry / Sale / Medication get entered_by and edited_by
  (set by the server, read-only to clients), filled in for older records from
  the change history. Shown as "Entered by" (and "edited by …") on the flock's
  entries, sales and medicines tables, and "by …" in the dashboard's last-entry
  column. No extra queries (page-speed tests unchanged).
- Users page explains what regions now do.
- Tests: test_entered_by (3), access matrix rewritten for the new rule
  (lists show every farm; dashboards/reports scoped; farm details still
  region-only), regions.spec rewritten (covering, scope switch, who entered).

### Edit window + admin approval of older changes  ✅ DONE
- Asked for: supervisors may change only recent records; older changes need an
  admin's approval with a reason; window configurable by admin (default 3 days).
- Settings → Rules (new, core/app_settings.py + AppSetting): "Edit window
  (days)", default 3 (today + 2 days before), 0 = no limit. Admin only to change.
- Daily entries, sales, medicines (core/edit_window.py, EditWindowMixin): a
  supervisor's add / change / delete dated before the window (or moving a
  record into it) returns "give a reason"; with a reason it becomes a
  ChangeRequest (values asked for + the record as it was) and nothing changes.
  Mistakes are shown at once, not at approval. Admins are never limited.
- Approve applies it as the supervisor's change through the same viewset
  checks (stock, live birds, bill lock); if it no longer fits, approval is
  refused with the reason and the request stays pending. Reject leaves the
  record. Each request records who asked, why, who decided and a note.
- Screens: reason dialog on the flock page (entries, sales, medicines, entry
  delete); "Waiting for admin approval" box on the flock; Approvals page in
  the admin menu (approve/reject, changes shown as "Mortality 3 → 9",
  recently decided list); dashboard alert + bell for the admin.
- Tests: test_edit_window (9), e2e edit-window.spec (4). Access-matrix and two
  e2e files that edit weeks-old entries turn the window off for themselves.
