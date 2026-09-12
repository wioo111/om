"""演练候选参数；保留连续区域、逐频道覆盖和失败恢复逻辑。"""
from strategy_v8 import AdaptiveV8

class FastScanP3(AdaptiveV8):
    name='FastScanP3'
    def __init__(self):
        super().__init__(cell_size=60.0,scan_fraction=0.20,probe_radius=80.0)

class CautiousP3(AdaptiveV8):
    name='CautiousP3'
    def __init__(self):
        super().__init__(probe_radius=35.0)

class CompactP3(AdaptiveV8):
    name='CompactP3'
    def __init__(self):
        super().__init__(cell_size=60.0,scan_fraction=0.20,probe_radius=40.0)
