def make_candidate(problem):
    if problem==3:
        from strategy_transit import ResidualP3
        return ResidualP3()
    if problem==4:
        from strategy_fast import FastP4
        return FastP4()
    raise ValueError('Only P3 and P4 practice are allowed')
