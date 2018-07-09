from ophyd.device import Device, Component as Cpt
from ophyd.signal import EpicsSignalRO, AttributeSignal

class FakeBeam(Device):
    fake_ipm2 = Cpt(EpicsSignalRO, 'XPP:VARS:FLOAT:01')
    fake_ipm3 = Cpt(EpicsSignalRO, 'XPP:VARS:FLOAT:02')
    fake_L3 = Cpt(EpicsSignalRO, 'XPP:VARS:FLOAT:03')
    
    def __init__(self, prefix='', name='fake_beam', **kwargs):
        super().__init__(prefix=prefix, name=name, **kwargs)

    @property
    def hints(self):
        return {'fields': [self.mj.name]}
    
# Need to write subscribe function