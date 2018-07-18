from ophyd.device import Device, Component as Cpt
from ophyd.signal import EpicsSignalRO, AttributeSignal

class FakeBeam(Device):
    # Event building does not work with the XPP:VARS:FLOAT: 
#     fake_ipm2 = Cpt(EpicsSignalRO, 'XPP:VARS:FLOAT:01')
#     fake_ipm3 = Cpt(EpicsSignalRO, 'XPP:VARS:FLOAT:02')
#     fake_L3 = Cpt(EpicsSignalRO, 'XPP:VARS:FLOAT:03')

    fake_ipm2 = Cpt(EpicsSignalRO, 'HX2:SB1:BMMON:_peakA_8')
    fake_ipm3 = Cpt(EpicsSignalRO, 'HX2:SB1:BMMON:_peakA_9')
    fake_L3 = Cpt(EpicsSignalRO, 'HX2:SB1:BMMON:_peakA_10')
    
    def __init__(self, prefix='', name='fake_beam', **kwargs):
        super().__init__(prefix=prefix, name=name, **kwargs)

    @property
    def hints(self):
        return {'fields': [self.mj.name]}
   
