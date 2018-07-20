from fake_beam import FakeBeam
from collections import deque

# Get live data
beam = FakeBeam()
ipm2List = deque()
ebeamList = deque()

def new_data(*args, **kwargs):
    global ipm2List, ebeamList
    ipm2 = beam.fake_ipm2.get()
    ebeam = beam.fake_L3.get()
    ipm2List.append(ipm2)
    ebeamList.append(ebeam)
