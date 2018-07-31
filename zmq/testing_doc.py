import sys
import zmq

import numpy as np
import holoviews as hv
import pandas as pd

from bokeh.layouts import layout, widgetbox, row, column
from bokeh.models import Button, Slider, Select, HoverTool, DatetimeTickFormatter
from bokeh.plotting import curdoc
from bokeh.io import output_file, save
from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from holoviews.streams import Buffer
import tables
from functools import partial
from collections import deque
import datetime

renderer = hv.renderer('bokeh').instance(mode='server')

def apply_formatter(plot, element):
    """
    Datetime formatting for x-axis ticks 
    
    """
    
    plot.handles['xaxis'].formatter = DatetimeTickFormatter(
        microseconds=['%D %H:%M:%S'], 
        milliseconds=['%D %H:%M:%S'], 
        seconds=["%D %H:%M:%S"],
        minsec=["%D %H:%M:%S"],
        minutes=['%D %H:%M:%S'], 
        hourmin=["%D %H:%M:%S"],
        hours=['%D %H:%M:%S'],
        days=['%D %H:%M:%S'], 
        months=['%D %H:%M:%S'], 
        years=['%D %H:%M:%S'])
    

def produce_graphs(context, doc):
    
    port = 5006
    socket = context.socket(zmq.SUB)
    # MUST BE FROM SAME MACHINE, CHANGE IF NECESSARY!!!
    socket.connect("tcp://psanagpu114:%d" % port)
    socket.setsockopt(zmq.SUBSCRIBE, b"")
        
    b_scatter = Buffer(pd.DataFrame({'timetool': []}), length=40000)
    b_IpmAmp = Buffer(pd.DataFrame({'ipm':[]}), length=1000)
    b_timehistory = Buffer(pd.DataFrame({'correlation':[]}), length=40000)
   
    hvScatter = hv.DynamicMap(
        hv.Points, streams=[b_scatter]).options(
        width=1000, finalize_hooks=[apply_formatter], xrotation=45).redim.label(
        index='Time in UTC')
    
    hvIpmAmp = hv.DynamicMap(
        hv.Scatter, streams=[b_IpmAmp]).options(
        width=500).redim.label(
        index='Timetool Data')
    
    hvTimeHistory = hv.DynamicMap(
        hv.Scatter, streams=[b_timehistory]).options(
        width=500, finalize_hooks=[apply_formatter], xrotation=45).redim.label(
        time='Time in UTC')
        
    layout = (hvIpmAmp+hvTimeHistory+hvScatter).cols(2)
    hvplot = renderer.get_plot(layout)
    cb_id_scatter = None
    cb_id_amp_ipm = None
    cb_id_timehistory = None
 
    def push_data_scatter(buffer):
        
        timetool_d = deque(maxlen=1000000)
        timetool_t = deque(maxlen=1000000)
        
        # Current bug, may need to have continuous stream of data?
        if socket.poll(timeout=0):
            stuff = socket.recv_pyobj()
            timetool_d = stuff['tt__FLTPOS_PS']
            
            timeData = deque(maxlen=1000000)
            for time in stuff['event_time']:
                num1 = str(time[0])
                num2 = str(time[1])
                fullnum = num1 + "." + num2
                timeData.append(float(fullnum))
                print("Scatter")
            timetool_t = timeData

        timeStuff = list(timetool_t)
        # Convert time to seconds so bokeh formatter can get correct datetime
        times = [1000*time for time in timeStuff]
            
        data = pd.DataFrame({'timestamp': times, 'timetool': timetool_d})
        data = data.set_index('timestamp')
        data.index.name = None
        buffer.send(data)
        print("Boop")
        
    def push_data_amp_ipm (buffer):
        
        timetool_d = deque(maxlen=1000000)
        ipm2_d = deque(maxlen=1000000)
        
        if socket.poll(timeout=0):
            stuff = socket.recv_pyobj()
            timetool_d = stuff['tt__AMPL']
            ipm2_d = stuff['ipm2__sum']

        data = pd.DataFrame({'timetool': timetool_d, 'ipm': ipm2_d})
        data = data.set_index('timetool')
        data.index.name = None
        
        buffer.send(data)
        print("Gottem")
        
    def push_data_correlation_time_history(buffer):
        
        timetool_d = deque(maxlen=1000000)
        timetool_t = deque(maxlen=1000000)
        ipm2_d = deque(maxlen=1000000)
        
        if socket.poll(timeout=0):
            stuff = socket.recv_pyobj()
            timetool_d = stuff['tt__FLTPOS_PS']
            ipm2_d = stuff['ipm2__sum']
            
            timeData = deque(maxlen=1000000)
            for time in stuff['event_time']:
                num1 = str(time[0])
                num2 = str(time[1])
                fullnum = num1 + "." + num2
                timeData.append(float(fullnum))
            timetool_t = timeData
        
        timeStuff = list(timetool_t)
        # Convert time to seconds so bokeh formatter can get correct datetime
        times = [1000*time for time in timeStuff]
        
        data = pd.DataFrame({'timetool': timetool_d, 'ipm': ipm2_d})
        
        data_list = data['timetool'].rolling(window=120).corr(other=data['ipm'])
        
        final_df = pd.DataFrame({
            'time': times[119:], 
            'correlation': data_list[119:]
        })
        
        final_df = final_df.set_index('time')
        final_df.index.name = None
        
        buffer.send(final_df)
        print("Heh")
    
#     def switch(attr, old, new):
#         """
#         Update drop down menu value
        
#         """
          # No non local in python 2!
#         global switch_key, b_timehistory, b_IpmAmp
#         switch_key = select.value
#         b_timehistory.clear()
#         b_IpmAmp.clear()
    
    cb_id_scatter = doc.add_periodic_callback(
        partial(push_data_scatter, 
                buffer=b_scatter), 
        1000)
    
    cb_id_amp_ipm = doc.add_periodic_callback(
        partial(push_data_amp_ipm,
                buffer=b_IpmAmp), 
        1000)
    
    cb_id_timehistory = doc.add_periodic_callback(
        partial(push_data_correlation_time_history, 
                buffer=b_timehistory), 
        1000)
    
    plot = hvplot.state
    doc.add_root(plot)
    
def launch_server():
   

    context = zmq.Context()

    origins = ["localhost:{}".format(5000)]
    
    apps = {'/': Application(FunctionHandler(partial(produce_graphs, context)))}
    server = Server(apps, port=5000)
    
    server.start()
    
    print('Opening Bokeh application on:')
    for entry in origins:
        print('\thttp://{}/'.format(entry))
 
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        print("terminating")
        server.io_loop.stop()
        
        
if __name__ == '__main__':
    launch_server()
