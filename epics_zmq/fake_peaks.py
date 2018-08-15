from ophyd.device import Device, Component as Cpt
from ophyd.signal import EpicsSignalRO, AttributeSignal

class FakeBeam(Device):

    peak_8 = Cpt(EpicsSignalRO, 'HX2:SB1:BMMON:_peakA_8')
    peak_9 = Cpt(EpicsSignalRO, 'HX2:SB1:BMMON:_peakA_9')
    peak_10 = Cpt(EpicsSignalRO, 'HX2:SB1:BMMON:_peakA_10')
    peak_11 = Cpt(EpicsSignalRO, 'HX2:SB1:BMMON:_peakA_11')
    peak_12 = Cpt(EpicsSignalRO, 'HX2:SB1:BMMON:_peakA_12')
    peak_13 = Cpt(EpicsSignalRO, 'HX2:SB1:BMMON:_peakA_13')
    peak_14 = Cpt(EpicsSignalRO, 'HX2:SB1:BMMON:_peakA_14')
    peak_15 = Cpt(EpicsSignalRO, 'HX2:SB1:BMMON:_peakA_15')
    
    def __init__(self, prefix='', name='fake_beam', **kwargs):
        super().__init__(prefix=prefix, name=name, **kwargs)
