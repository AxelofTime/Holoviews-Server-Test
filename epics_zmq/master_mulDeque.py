import sys
import time
import socket

import numpy as np
import holoviews as hv
import pandas as pd

from fake_peaks import FakeBeam
from functools import partial
from collections import deque
import statistics
import zmq


def new_data(*args, **kwargs):
    """
    Append data from subscribe into data containers
    
    """
    global oldTime
    
    kwargs['in_value'].append(kwargs['value'])
    kwargs['in_time'].append(kwargs['timestamp'])
    kwargs['temp'].append(kwargs['value'])
    
    if time.time() - oldTime > 1:
        kwargs['median'].append(statistics.median(kwargs['temp']))
        kwargs['stdev'].append(statistics.stdev(kwargs['temp']))
        kwargs['medianTS'].append(kwargs['timestamp'])
        kwargs['temp'].clear()
        oldTime = time.time()
        print(kwargs['median'])
        print(kwargs['stdev'])
    
    
def launch_server():

    global oldTime
    oldTime = time.time()
    port = "5000"
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:%s" % port)
    
    maxlen = 500000
    full_maxlen = 2000000
    
    # Get data
    beam = FakeBeam()
    peak_8 = deque(maxlen=maxlen)
    peak_8_TS = deque(maxlen=maxlen)
    peak_9 = deque(maxlen=maxlen)
    peak_9_TS = deque(maxlen=maxlen)
    peak_10 = deque(maxlen=maxlen)
    peak_10_TS = deque(maxlen=maxlen)
    
    peak_8_median = deque(maxlen=full_maxlen)
    peak_9_median = deque(maxlen=full_maxlen)
    peak_10_median = deque(maxlen=full_maxlen)
    
    peak_8_std = deque(maxlen=full_maxlen)
    
    peak_8_median_TS = deque(maxlen=full_maxlen) # Maybe use this for stdev too?
    
    peak_8_temp = []
    peak_9_temp = []
    peak_10_temp = []

    
    # Subscribe to devices
    beam.peak_8.subscribe(
        partial(new_data, 
                in_value=peak_8, 
                in_time=peak_8_TS, 
                temp=peak_8_temp, 
                median=peak_8_median,
                stdev=peak_8_std,
                medianTS=peak_8_median_TS)
    )
    
#     beam.peak_9.subscribe(
#         partial(new_data, in_value=peak_9, in_time=peak_9_TS, temp=peak_9_temp)
#     )
    
#     beam.peak_10.subscribe(
#         partial(new_data, in_value=peak_10, in_time=peak_10_TS, temp=peak_10_temp)
#     )
    
    peakDict = {
        'peak_8':peak_8, 
        #'peak_9':peak_9, 
        #'peak_10':peak_10, 
        
    }
    peakTSDict = {
        'peak_8_TS':peak_8_TS, 
        #'peak_9_TS':peak_9_TS, 
        #'peak_10_TS':peak_10_TS, 
        
    }
    medianDict = {
        'peak_8_median':peak_8_median,
    }
    stdevDict = {
        'peak_8_std':peak_8_std,
    }
    median_stdevDict={
        'peak_8_std_median_TS':peak_8_median_TS
    }
    
    data = {
        'peakDict':peakDict,
        'peakTSDict':peakTSDict,
        'medianDict':medianDict,
        'stdevDict':stdevDict,
        'median_stdevDict':median_stdevDict
    }
    
    # Send data a half second intervals
    while True:
#         socket.send_pyobj(data)
#         print(len(data['peakTSDict']['peak_8_TS']))
#         time.sleep(1)
        
        message = socket.recv()
        print("Received request: ", message)
        socket.send_pyobj(data)
        
if __name__ == '__main__':
    launch_server()