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
- Bugs found & fixed (both in the new code, caught by tests):
  BUG-003 Decimal*float in cost calc (coerced config rates via D());
  BUG-004 ROUND_HALF_UP not imported in data.py (added). NOTE for release
  cherry-pick: ensure ROUND_HALF_UP import exists in reports.py too.
