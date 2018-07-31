from ophyd.device import Device, Component as Cpt
from ophyd.signal import EpicsSignalRO, AttributeSignal

class FakeTimetool(Device):

    fake_timetool = Cpt(EpicsSignalRO, 'XPP:TIMETOOL:TTALL')
    
    def __init__(self, prefix='', name='fake_beam', **kwargs):
        super().__init__(prefix=prefix, name=name, **kwargs)

    @property
    def hints(self):
        return {'fields': [self.mj.name]}
    