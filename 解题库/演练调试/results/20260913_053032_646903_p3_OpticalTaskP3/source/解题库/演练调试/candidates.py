def make_candidate(problem):
    if problem==3:
        from strategy_task import OpticalTaskP3
        return OpticalTaskP3()
    if problem==4:
        from strategy_fast import FastP4
        return FastP4()
    raise ValueError('Only P3 and P4 practice are allowed')
