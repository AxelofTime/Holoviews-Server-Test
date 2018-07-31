import numpy as np
import holoviews as hv
import pandas as pd

import sys
from bokeh.io import show
from bokeh.layouts import layout, widgetbox, row, column
from bokeh.models import Button, Slider, Select, HoverTool, DatetimeTickFormatter
from bokeh.plotting import curdoc
from bokeh.io import output_file, save
from bokeh.server.server import Server
from bokeh.application import Application
from holoviews.streams import Buffer
import tables
from fake_timetool_beam import FakeTimetool
from fake_beam import FakeBeam
from functools import partial
from collections import deque
from event_builder import basic_event_builder

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


def produce_graphs(doc, timetool_d, timetool_t, ipm2_d, ipm2_t, ipm3_d, ipm3_t):
    
    switch_key = 'ipm2'
    
    b_scatter = Buffer(pd.DataFrame({'timetool_data':[]}), length=40000)
    b_IpmAmp = Buffer(pd.DataFrame({'timetool':[], 'ipm':[]}), length=1000)
    b_timehistory = Buffer(pd.DataFrame({'time':[], 'correlation':[]}), length=40000)

    hvScatter = hv.DynamicMap(
        partial(hv.Points), streams=[b_scatter]).options(
        width=1000, finalize_hooks=[apply_formatter], xrotation=45).redim.label(
        index='Time in UTC')
    
    hvIpmAmp = hv.DynamicMap(
        partial(hv.Scatter, kdims=['timetool', 'ipm']), streams=[b_IpmAmp]).options(
        width=500).redim.label(
        time='Time in UTC')
    
    hvTimeHistory = hv.DynamicMap(
        partial(hv.Scatter, kdims=['time', 'correlation']), streams=[b_timehistory]).options(
        width=500, finalize_hooks=[apply_formatter], xrotation=45).redim.label(
        time='Time in UTC')
    
    layout = (hvIpmAmp+hvTimeHistory+hvScatter).cols(2)
    
    hvplot = renderer.get_plot(layout, doc)
    cb_id_scatter = None
    cb_id_amp_ipm = None
    cb_id_timehistory = None
    
    def push_data_scatter(timetool_d, timetool_t, buffer):
        
        timeStuff = list(timetool_t)
        # Convert time to seconds so bokeh formatter can get correct datetime
        times = [1000*time for time in timeStuff]
        
        edgePos = []
        for array in timetool_d:
            edgePos.append(array[1])
            
        edgePos_data = pd.Series(edgePos, index=times)
        zipped = basic_event_builder(timetool_data=edgePos_data)
        buffer.send(zipped)
        
    def push_data_amp_ipm (timetool_d, timetool_t, ipm2_d, ipm2_t, ipm3_d, ipm3_t, buffer):
        
        timeStuff = list(timetool_t)
        # Convert time to seconds so bokeh formatter can get correct datetime
        times = [1000*time for time in timeStuff]
        
        tt_d = list(timetool_d)
        tt_t = list(timetool_t)
        i2_d = list(ipm2_d)
        i2_t = list(ipm2_t)
        i3_d = list(ipm3_d)
        i3_t = list(ipm3_t)
        
        ipmValue = i2_d
        ipmTime = i2_t
        
        if switch_key == 'ipm2':
            ipmValue = i2_d
            ipmTime = i2_t
        elif switch_key == 'ipm3':
            ipmValue = i3_d
            ipmTime = i3_t
        
        if len(tt_d) > len(ipmValue):
            tt_d = tt_d[:len(ipmValue)]
            tt_t = tt_t[:len(ipmValue)]
        elif len(tt_d) < len(ipmValue):
            ipmValue = ipmValue[:len(tt_d)]
            ipmTime = ipmTime[:len(tt_d)]
        
        edgeAmp = []
        
        for array in tt_d:
            edgeAmp.append(array[2])
            
        data = pd.DataFrame({'timetool': edgeAmp, 'ipm': ipmValue})
        
        buffer.send(data)
               
        
    def push_data_correlation_time_history(timetool_d, timetool_t, ipm2_d, ipm2_t, ipm3_d, ipm3_t, buffer):
        
        timeStuff = list(timetool_t)
        # Convert time to seconds so bokeh formatter can get correct datetime
        times = [1000*time for time in timeStuff]
        
        tt_d = list(timetool_d)
        tt_t = list(timetool_t)
        i2_d = list(ipm2_d)
        i2_t = list(ipm2_t)
        i3_d = list(ipm3_d)
        i3_t = list(ipm3_t)
        
        ipmValue = i2_d
        ipmTime = i2_t
        
        if switch_key == 'ipm2':
            ipmValue = i2_d
            ipmTime = i2_t
        elif switch_key == 'ipm3':
            ipmValue = i3_d
            ipmTime = i3_t
        
        if len(tt_d) > len(ipmValue):
            tt_d = tt_d[:len(ipmValue)]
            tt_t = tt_t[:len(ipmValue)]
        elif len(tt_d) < len(ipmValue):
            ipmValue = ipmValue[:len(tt_d)]
            ipmTime = ipmTime[:len(tt_d)]
        
        edgeAmp = []
        
        for array in tt_d:
            edgeAmp.append(array[2])
        
        data = pd.DataFrame({'timetool': edgeAmp, 'ipm': ipmValue})
        
        data_list = data['timetool'].rolling(window=120).corr(other=data['ipm'])
        
        final_df = pd.DataFrame({
            'time': times[119:], 
            'correlation': data_list[119:]
        })
        
        #print(final_df)
        
        buffer.send(final_df)
    
    def switch(attr, old, new):
        """
        Update drop down menu value
        
        """
        
        nonlocal switch_key, b_timehistory, b_IpmAmp
        switch_key = select.value
        b_timehistory.clear()
        b_IpmAmp.clear()
        print(switch_key)
    
    select = Select(title='ipm value:', value='ipm2', options=['ipm2', 'ipm3'])
    select.on_change('value', switch)
    
    cb_id_scatter = doc.add_periodic_callback(
        partial(push_data_scatter, 
                timetool_d=timetool_d, 
                timetool_t=timetool_t, 
                buffer=b_scatter), 
        1000)
    
    cb_id_amp_ipm = doc.add_periodic_callback(
        partial(push_data_amp_ipm,
                timetool_d=timetool_d, 
                timetool_t=timetool_t,
                ipm2_d=ipm2_d,
                ipm2_t=ipm2_t,
                ipm3_d=ipm3_d,
                ipm3_t=ipm3_t,
                buffer=b_IpmAmp), 
        1000)
    
    cb_id_timehistory = doc.add_periodic_callback(
        partial(push_data_correlation_time_history, 
                timetool_d=timetool_d, 
                timetool_t=timetool_t,
                ipm2_d=ipm2_d,
                ipm2_t=ipm2_t,
                ipm3_d=ipm3_d,
                ipm3_t=ipm3_t,
                buffer=b_timehistory), 
        1000)
    
    plot = column(select, hvplot.state)
    doc.add_root(plot)

def new_data(*args, **kwargs):
    """
    Append data from subscribe into data containers
    
    """
    
    kwargs['in_value'].append(kwargs['value'])
    kwargs['in_time'].append(kwargs['timestamp'])
    

def launch_server():
   
    maxlen = 1000000
    
    # Initialize data carriers
    timetool = FakeTimetool()
    ipm = FakeBeam()

    timetool_d = deque(maxlen=maxlen)
    timetool_t = deque(maxlen=maxlen)
    ipm2_d = deque(maxlen=maxlen)
    ipm2_t = deque(maxlen=maxlen)
    ipm3_d = deque(maxlen=maxlen)
    ipm3_t = deque(maxlen=maxlen)
    
    timetool.fake_timetool.subscribe(
        partial(new_data, in_value=timetool_d, in_time=timetool_t)
    )
    
    ipm.fake_ipm2.subscribe(
        partial(new_data, in_value=ipm2_d, in_time=ipm2_t)
    )
    
    ipm.fake_ipm3.subscribe(
        partial(new_data, in_value=ipm3_d, in_time=ipm3_t)
    )
    origins = ["localhost:{}".format(5006)]
    
    server = Server(
        {
            '/Testing': partial(
                produce_graphs,
                timetool_d=timetool_d,
                timetool_t=timetool_t,
                ipm2_d=ipm2_d,
                ipm2_t=ipm2_t,
                ipm3_d=ipm3_d,
                ipm3_t=ipm3_t
            )
        },
        allow_websocket_origin=origins,
        # num_procs must be 1 for tornado loops to work correctly 
        num_procs=1,
    )
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
