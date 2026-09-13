def make_candidate(problem):
    if problem==3:
        from strategy_task import OpticalTaskP3
        return OpticalTaskP3()
    if problem==4:
        from strategy_route_probe import RouteProbeP4
        return RouteProbeP4()
    raise ValueError('Only P3 and P4 practice are allowed')
