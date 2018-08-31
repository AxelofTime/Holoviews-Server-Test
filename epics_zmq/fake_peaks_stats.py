from ophyd.device import Device, Component as Cpt

from listsig import StatsEpicsSignal

#from ophyd.signal import EpicsSignalRO, AttributeSignal

class FakeBeam(Device):
    
    peak_8 = Cpt(StatsEpicsSignal, 'XPP:SB2:BMMON:AMPL_8')
    peak_9 = Cpt(StatsEpicsSignal, 'XPP:SB2:BMMON:SUM')
    peak_10 = Cpt(StatsEpicsSignal, 'XPP:SB3:BMMON:SUM')
        
    def __init__(self, prefix='', name='fake_beam', **kwargs):
        super().__init__(prefix=prefix, name=name, **kwargs)
