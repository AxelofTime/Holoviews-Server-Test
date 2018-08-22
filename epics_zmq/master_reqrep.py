import sys
import time
import socket

import numpy as np
import holoviews as hv
import pandas as pd

from fake_peaks import FakeBeam
from functools import partial
from collections import deque
import zmq


def new_data(*args, **kwargs):
    """
    Append data from subscribe into data containers
    
    """
    
    kwargs['in_value'].append(kwargs['value'])
    kwargs['in_time'].append(kwargs['timestamp'])
    
    
def launch_server():

    port = "5000"
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:%s" % port)
    
    maxlen = 1000000
    
    # Get data
    beam = FakeBeam()
    peak_8 = deque(maxlen=maxlen)
    peak_8_TS = deque(maxlen=maxlen)
    peak_9 = deque(maxlen=maxlen)
    peak_9_TS = deque(maxlen=maxlen)
    peak_10 = deque(maxlen=maxlen)
    peak_10_TS = deque(maxlen=maxlen)
    peak_11 = deque(maxlen=maxlen)
    peak_11_TS = deque(maxlen=maxlen)
    peak_12 = deque(maxlen=maxlen)
    peak_12_TS = deque(maxlen=maxlen)
    peak_13 = deque(maxlen=maxlen)
    peak_13_TS = deque(maxlen=maxlen)
    peak_14 = deque(maxlen=maxlen)
    peak_14_TS = deque(maxlen=maxlen)
    peak_15 = deque(maxlen=maxlen)
    peak_15_TS = deque(maxlen=maxlen)
    
    # Subscribe to devices
    beam.peak_8.subscribe(
        partial(new_data, in_value=peak_8, in_time=peak_8_TS)
    )
    
    beam.peak_9.subscribe(
        partial(new_data, in_value=peak_9, in_time=peak_9_TS)
    )
    
    beam.peak_10.subscribe(
        partial(new_data, in_value=peak_10, in_time=peak_10_TS)
    )
    
    beam.peak_11.subscribe(
        partial(new_data, in_value=peak_11, in_time=peak_11_TS)
    )
    
    beam.peak_12.subscribe(
        partial(new_data, in_value=peak_12, in_time=peak_12_TS)
    )
    
    beam.peak_13.subscribe(
        partial(new_data, in_value=peak_13, in_time=peak_13_TS)
    )
    
    beam.peak_14.subscribe(
        partial(new_data, in_value=peak_14, in_time=peak_14_TS)
    )
    
    beam.peak_15.subscribe(
        partial(new_data, in_value=peak_15, in_time=peak_15_TS)
    )
    
   
    peakDict = {
        'peak_8':peak_8, 
        'peak_9':peak_9, 
        'peak_10':peak_10, 
        'peak_11':peak_11, 
        'peak_12':peak_12, 
        'peak_13':peak_13,
        'peak_14':peak_14,
        'peak_15':peak_15
    }
    peakTSDict = {
        'peak_8_TS':peak_8_TS, 
        'peak_9_TS':peak_9_TS, 
        'peak_10_TS':peak_10_TS, 
        'peak_11_TS':peak_11_TS, 
        'peak_12_TS':peak_12_TS, 
        'peak_13_TS':peak_13_TS,
        'peak_14_TS':peak_14_TS,
        'peak_15_TS':peak_15_TS
    }
    
    data = {
        'peakDict':peakDict,
        'peakTSDict':peakTSDict
    }
    
    # Send data a half second intervals
    while True:
        
        message = socket.recv()
        print("Received request: ", message)
        time.sleep(1)
        socket.send_pyobj(data)
        
if __name__ == '__main__':
    launch_server()
