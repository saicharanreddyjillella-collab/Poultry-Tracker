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


## 3.4 — Daily bird-population reconciliation

## 3.2 — Breed-standard weight variance

## 3.5 — Unified performance scorecard

## 3.6 — Water:feed ratio + deviation alert

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
