# Machine A Deliverable — Round 01

Best candidate: A04 (label). Run on 2026-09-12 against the 21-case development suite
(collab/screen.json). All 21 cases fully cleared, no errors, no stop-reason regressions.

## Files
- `route_candidate.py` — RouteCandidate / RouteMixin overriding v8 route methods.
- `A04.json` — paired comparison report (baseline vs A04) from `collab.bench run`.
- `A04_worst_trace.json` — slowest case trace (N10_00, 3239.1 s).

## Five-line change description

1. **What changed**: rewrote `_route` to mirror v8 exactly (NN + 2-opt with `start` as
   i=0 prev), plus an or-opt single-node relocate; overrode `_cover_route` to evaluate
   powers `(1.0, 1.6)` only with station penalty `4 * n_unknown` (v8 uses `(0.6, 1.0, 1.6)`
   with penalty `6 * n_unknown`).
2. **Why expected to help**: move time dominates (177.7 s of 252.9 s per source). On
   sparse N=10 cases v8's power=0.6 routes under-cover and force long detours; the
   denser power=1.6 routes combined with a lower station penalty let them compete fairly.
3. **Average improvement**: 1.23% (paired_delta = -3.10 s/source; 252.57 -> 249.48).
4. **P95 and full-clear**: P95 dropped from 318.58 s to 309.75 s (-8.83 s, -2.8%);
   all 21 cases fully cleared, zero exceptions.
5. **Known issues**: N=11 regresses by 2.56% on average (one case +19.6 s) because
   power=0.6 is no longer evaluated; N=14/15 unchanged since v8 already clears them
   without supplemental stations. Did not reach the 3% screening threshold.

## Per-N breakdown
- N=10: -18.51 s/source (5.88% better) — three cases, biggest win
- N=11: +6.53 s/source (2.56% worse)
- N=12: -3.08 s/source (1.08% better)
- N=13: -6.03 s/source (2.35% better)
- N=14: 0.0 s/source (no change)
- N=15: 0.0 s/source (no change)
- N=16: -0.58 s/source (0.29% better)

## Reproducing

```powershell
python -X utf8 -m collab.bench run `
  --candidate collab.route_candidate:make_strategy `
  --role A `
  --label A04
```

Cache note: this machine is Python 3.13.5 / numpy 2.1.3, so collab/cache is rebuilt
each run (no matching entry for the frozen 3.14.4 / 2.4.4 baseline). The paired
comparison is still valid because `collab.bench` regenerates and caches v8 with the
local environment, then compares candidate against that fresh v8 baseline. On C's
frozen environment the baseline cache will be reused; verify the new hash matches.
