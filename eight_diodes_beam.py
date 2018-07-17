from ophyd.device import Device, Component as Cpt
from ophyd.signal import EpicsSignalRO, AttributeSignal

class FakeEightBeams(Device):

    fake_dcc = Cpt(EpicsSignalRO, 'XCS:SND:DIA:DCC:DIODE')
    fake_dci = Cpt(EpicsSignalRO, 'XCS:SND:DIA:DCI:DIODE')
    fake_dco = Cpt(EpicsSignalRO, 'XCS:SND:DIA:DCO:DIODE')
    fake_dd = Cpt(EpicsSignalRO, 'XCS:SND:DIA:DD:DIODE')
    fake_di = Cpt(EpicsSignalRO, 'XCS:SND:DIA:DI:DIODE')
    fake_do = Cpt(EpicsSignalRO, 'XCS:SND:DIA:DO:DIODE')
    fake_t1d = Cpt(EpicsSignalRO, 'XCS:SND:DIA:T1:DIODE')
    fake_t4d = Cpt(EpicsSignalRO, 'XCS:SND:DIA:T4:DIODE')    
   
    def __init__(self, prefix='', name='fake_beam', **kwargs):
        super().__init__(prefix=prefix, name=name, **kwargs)

    @property
    def hints(self):
        return {'fields': [self.mj.name]}
    