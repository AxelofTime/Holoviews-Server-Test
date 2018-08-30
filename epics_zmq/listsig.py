import time

import numpy as np
from ophyd.signal import EpicsSignal


class StatsEpicsSignal(EpicsSignal):
    SUB_STATS = 'stats'
    _default_sub = SUB_STATS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._values_acc = []
        self._ts_start = None

    def subscribe(self, callback, event_type=None, run=True):
        self._ts_start = time.time()
        def temp(*args, **kwargs):
            pass
        super().subscribe(temp, event_type=self.SUB_VALUE, run=False)
        super().subscribe(callback, event_type=event_type, run=run)

    def _read_changed(self, value=None, timestamp=None, **kwargs):
        super()._read_changed(value=value, timestamp=timestamp, **kwargs)
        self._values_acc.append(value)
        if timestamp - self._ts_start > 1:
            self._run_subs(sub_type=self.SUB_STATS,
                           median_value=np.median(self._values_acc),
                           std_value = np.std(self._values_acc),
                           timestamp=(timestamp + self._ts_start) / 2)
            self._values_acc.clear()
            self._ts_start = time.time()