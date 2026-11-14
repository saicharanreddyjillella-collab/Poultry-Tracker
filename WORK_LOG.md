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

## 3.3 — Culling separate from mortality  ⏳ NEXT

## 3.4 — Daily bird-population reconciliation

## 3.2 — Breed-standard weight variance

## 3.5 — Unified performance scorecard

## 3.6 — Water:feed ratio + deviation alert

---
## Registered bugs
(none yet)
