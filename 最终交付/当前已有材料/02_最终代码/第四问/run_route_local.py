"""Explicit standalone OFFLINE P4 runner. Never opens a simulator HTTP endpoint."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import random
import sys
import traceback


NORMAL_STOP_REASONS = {'all_channels_cleared_or_covered', 'cleared_maximum_16'}
COST_KEYS = ('move_time_s', 'switch_time_s', 'measure_time_s', 'clear_time_s')


def _make(name):
    if name == 'RouteProbeP4':
        from strategy_route_probe import RouteProbeP4
        return RouteProbeP4()
    if name == 'RouteAwareP4':
        from strategy_route import RouteAwareP4
        return RouteAwareP4()
    if name == 'FastP4':
        from strategy_fast import FastP4
        return FastP4()
    if name == 'FinishP4':
        from strategy_finish import FinishP4
        return FinishP4(enabled=True, trim_corners=True)
    from strategy_hunt import HuntP4
    return HuntP4()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strategy', choices=('RouteProbeP4', 'RouteAwareP4', 'HuntP4', 'FastP4', 'FinishP4'), default='RouteProbeP4')
    parser.add_argument('--seed', type=int, default=993201)
    parser.add_argument('--N', '--n-sources', dest='n_sources', type=int, default=10)
    parser.add_argument('--dir-frac', type=float, default=0.5)
    parser.add_argument('--error-mode', choices=('random', 'fixed', 'edge'), default='fixed')
    parser.add_argument('--reception-range', nargs=2, type=float, metavar=('MIN', 'MAX'), default=(1000.0, 1500.0))
    parser.add_argument('--max-steps', type=int, default=8000)
    parser.add_argument('--output', type=Path, help='Optional new JSON file containing the complete action log')
    args = parser.parse_args(argv)
    if not 10 <= args.n_sources <= 16:
        parser.error('--N must be within 10..16')
    if not 0 <= args.dir_frac <= 1:
        parser.error('--dir-frac must be within 0..1')
    lo, hi = args.reception_range
    if not 1000 <= lo <= hi <= 1500:
        parser.error('--reception-range must stay within 1000..1500')
    if args.max_steps < 1:
        parser.error('--max-steps must be positive')
    if args.output is not None and args.output.exists():
        parser.error('--output must be a new file; existing evidence is not overwritten')

    from mock_simulator_p4 import P4MockSimulator
    from robot_iter import run_with_sim_strategy

    random.seed(args.seed)
    strategy = _make(args.strategy)
    source = Path(inspect.getfile(type(strategy))).resolve()
    loaded = dict(actual_class=type(strategy).__name__, name=strategy.name,
                  source=str(source), sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    print('[OFFLINE P4 LOADED] ' + json.dumps(loaded, ensure_ascii=False), flush=True)
    scenario = dict(seed=args.seed, N=args.n_sources, dir_frac=args.dir_frac,
                    error_mode=args.error_mode, reception_range=list(args.reception_range))
    print('[OFFLINE P4 SCENARIO] ' + json.dumps(scenario), flush=True)
    sim = P4MockSimulator(seed=args.seed, n_sources=args.n_sources, dir_frac=args.dir_frac,
                          error_mode=args.error_mode, reception_range=args.reception_range)
    costs = dict.fromkeys(COST_KEYS, 0.0)

    class AccountedMock:
        def enter(self): return sim.enter()
        def exit(self): return sim.exit()
        def stats(self): return sim.stats()
        def _action(self, kind, x, y, channel):
            import math
            old_pos, old_ch = sim.pos, sim.ch
            response = getattr(sim, kind)(x, y, channel)
            costs['move_time_s'] += math.dist(old_pos, (x, y)) / 5.0
            if kind == 'measure':
                costs['switch_time_s'] += float(old_ch != channel)
                costs['measure_time_s'] += 5.0
            else:
                costs['clear_time_s'] += 5.0 if response['clear_result'] == 'success' else 3.0
            return response
        def measure(self, x, y, ch): return self._action('measure', x, y, ch)
        def clear(self, x, y, ch): return self._action('clear', x, y, ch)

    error = None
    try:
        result = run_with_sim_strategy(strategy, AccountedMock(), max_steps=args.max_steps)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        traceback.print_exc(file=sys.stderr)
        result = dict(cleared=len(sim.cleared), virtual_time_s=sim.virtual_time_s,
                      stop_reason='runner_error', time_breakdown=costs.copy(),
                      error=error, partial_log_unavailable=True)
    full_clear = result['cleared'] == args.n_sources
    normal_stop = result['stop_reason'] in NORMAL_STOP_REASONS
    accounting_ok = abs(sum(costs.values()) - result['virtual_time_s']) < 1e-6
    accepted = full_clear and normal_stop and error is None and accounting_ok
    summary = dict(loaded=loaded, scenario=scenario, full_clear=full_clear,
                   normal_stop=normal_stop, accepted_run=accepted, accounting_ok=accounting_ok,
                   cleared=result['cleared'], stop_reason=result['stop_reason'],
                   virtual_time_s=result['virtual_time_s'],
                   T_per_N=result['virtual_time_s'] / args.n_sources,
                   time_breakdown=costs, diagnostics=strategy.diagnostics() if hasattr(strategy, 'diagnostics') else {})
    if error:
        summary['error'] = error
    print('[OFFLINE P4 COSTS] ' + json.dumps(costs, ensure_ascii=False), flush=True)
    print('[OFFLINE P4 SUMMARY] ' + json.dumps(summary, ensure_ascii=False, allow_nan=False), flush=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as handle:
            json.dump(dict(summary=summary, result=result), handle, ensure_ascii=False, indent=2, allow_nan=False)
        print('[OFFLINE P4 EVIDENCE] ' + str(args.output.resolve()), flush=True)
    return 0 if accepted else 1


if __name__ == '__main__':
    raise SystemExit(main())
