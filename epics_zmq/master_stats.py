import sys
import time
import socket

import numpy as np
import holoviews as hv
import pandas as pd

from fake_peaks_stats import FakeBeam
from functools import partial
from collections import deque
import statistics
import zmq


# Move everything into a class
# Or use a list/dictionary instead of multiple timers
def new_data(*args, **kwargs):
    """
    Append data from subscribe into data containers
    
    """    
    print('hmmm')
    kwargs['median'].append(kwargs['median_value'])
    kwargs['stdev'].append(kwargs['std_value'])
    kwargs['medianTS'].append(kwargs['timestamp'])
    print(kwargs['stdev'])
    
    
def launch_server():
    
    beam = FakeBeam()
    port = "5000"
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:%s" % port)
    
    full_maxlen = 2000000
    
    # Get data
   
    peak_8_median = deque(maxlen=full_maxlen)
    peak_9_median = deque(maxlen=full_maxlen)
    peak_10_median = deque(maxlen=full_maxlen)
    
    peak_8_std = deque(maxlen=full_maxlen)
    peak_9_std = deque(maxlen=full_maxlen)
    peak_10_std = deque(maxlen=full_maxlen)
    
    peak_8_median_TS = deque(maxlen=full_maxlen) # Maybe use this for stdev too?
    peak_9_median_TS = deque(maxlen=full_maxlen)
    peak_10_median_TS = deque(maxlen=full_maxlen)
    
    
    # Subscribe to devices
    beam.peak_8.subscribe(
        partial(new_data, 
                median=peak_8_median,
                stdev=peak_8_std,
                medianTS=peak_8_median_TS)
    )
    
    beam.peak_9.subscribe(
        partial(new_data, 
                median=peak_9_median,
                stdev=peak_9_std,
                medianTS=peak_9_median_TS)
    )
    
    beam.peak_10.subscribe(
        partial(new_data, 
                median=peak_10_median,
                stdev=peak_10_std,
                medianTS=peak_10_median_TS)
    )
   
    medianDict = {
        'peak_8_median':peak_8_median,
        'peak_9_median':peak_9_median,
        'peak_10_median':peak_10_median
    }
    stdevDict = {
        'peak_8_std':peak_8_std,
        'peak_9_std':peak_9_std,
        'peak_10_std':peak_10_std
    }
    median_stdev_TS_Dict={
        'peak_8_std_median_TS':peak_8_median_TS,
        'peak_9_std_median_TS':peak_9_median_TS,
        'peak_10_std_median_TS':peak_10_median_TS
    }
    
    data = {
        'medianDict':medianDict,
        'stdevDict':stdevDict,
        'median_stdev_TS_Dict':median_stdev_TS_Dict
    }
    
    # Keep sending data
    while True:

        message = socket.recv()
        socket.send_pyobj(data)
        
if __name__ == '__main__':
    launch_server()
