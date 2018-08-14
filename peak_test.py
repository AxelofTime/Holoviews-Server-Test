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
import tables
from fake_peaks import FakeBeam
from functools import partial
from collections import deque
from event_builder import basic_event_builder
from holoviews.streams import Buffer
from holoviews.core import util
from holoviews.operation.datashader import datashade, dynspread
from holoviews.operation import decimate

import time

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
    
def gen_spikes(df):
    return hv.Spikes(df).options(
        width=1000, finalize_hooks=[apply_formatter], apply_ranges=False)#.options(apply_ranges=False)

def gen_labels(df):
    
    labels = hv.Labels(
        {('x', 'y'): df[['x', 'y']], 'text': list(df['labels'])}, ['x', 'y'], 'text').options(
        xoffset=0.2, yoffset=0.05)#, apply_ranges=False)
    
    return labels
    
def produce_timehistory(doc, peak, peakTS):
    # Streams
    
    # See if you can limit the buffer
    b_th_peak = Buffer(pd.DataFrame({'peak':[], 'lowerbound':[], 'higherbound':[]}), length=1000000)
    b_th_peak_std = Buffer(pd.DataFrame({'peak':[], 'lowerbound':[], 'higherbound':[]}), length=1000000)

    s_spikes = Buffer(pd.DataFrame({'y':[]}), length=1000000)
    s_labels = Buffer(pd.DataFrame({'x':[], 'y':[]}), length=1000000)
    s_spikes_end = Buffer(pd.DataFrame({'y':[]}), length=1000000)
    
    #s_spikes = hv.streams.Stream.define('df', df=pd.DataFrame({'location':[], 'y':[]}))()
    #s_labels = hv.streams.Stream.define('df', df=pd.DataFrame({'x':[], 'y':[], 'labels':[]}))()
        
    # Generate dynamic map
    
    plot_peak_b = hv.DynamicMap(partial(
        hv.Points, kdims=['index', 'peak']),
        streams=[b_th_peak]).options(
        width=1000, finalize_hooks=[apply_formatter]).redim.label(
        index='Time in UTC')
    
    # HoloViews seems to currently have a bug with hv.Spread with buffers, once it is fixed
    # we can try to implement hv.spread instead of this
    plot_peak_std_low = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'lowerbound']), streams=[b_th_peak]).options(
        line_alpha=0.5, line_color='gray').redim.label(
        index='Time in UTC')
    
    plot_peak_std_high = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'higherbound']), streams=[b_th_peak]).options(
        line_alpha=0.5, line_color='gray').redim.label(
        index='Time in UTC')
    
    #hvSpikes = hv.DynamicMap(gen_spikes, streams=[s_spikes])
    #hvLabels = hv.DynamicMap(gen_labels, streams=[s_labels])
    hvSpikes = hv.DynamicMap(partial(hv.Spikes), streams=[s_spikes]).options(
        apply_ranges=False, color='green')
    hvSpikes_end = hv.DynamicMap(hv.Spikes, streams=[s_spikes_end]).options(
        apply_ranges=False, color='red')
    hvLabels = hv.DynamicMap(partial(hv.Labels, kdims=['x','y']), streams=[s_labels]).options(apply_ranges=False)
    
    #testing = datashade(plot_ipm_b).options(width = 1000)
    test1 = datashade(plot_peak_std_low, streams=[hv.streams.PlotSize], normalization='linear').options(
        width=1000, finalize_hooks=[apply_formatter])
    #.opts(norm=dict(framewise=True))
    test2 = datashade(plot_peak_std_high, streams=[hv.streams.PlotSize], normalization='linear')
    #.opts(norm=dict(framewise=True))
    pointTest = decimate(plot_peak_b, streams=[hv.streams.PlotSize], normalization='linear')
    
    
    # Scrolling after pausing the graph seems to cause Parameter name clashes for keys: {'height', 'width', 'scale'} error!
    
    #plot = (plot_ipm_b*plot_ipm_std_low*plot_ipm_std_high)
    plot = (pointTest*test1*test2*hvSpikes*hvLabels*hvSpikes_end)
    #plot=hvSpikes*hvLabels
    
    # Use bokeh to render plot
    hvplot = renderer.get_plot(plot, doc)
    
    switch_key = 'peak_8'
    start = [1534280820000, 1534271880000]
    end  = [1534279380000, 1534272000000]
    labels = ['Test 1', 'Test 2']
    medianCheck = 0
    
    # For pushing in data, maybe cut off first 119 points to get rid of those weird extremes
    def push_data(stream):
                
        TS_key = switch_key + '_TS'
        data = list(peak[switch_key])
        timestamp = list(peakTS[TS_key])
       
        times = [1000*time for time in timestamp]
        dataSeries = pd.Series(data, index=times)
        
        zipped = basic_event_builder(peak=dataSeries)
        median = zipped.rolling(120, min_periods=1).median()
        std = zipped.rolling(120, min_periods=1).std()
        lowerbound = median - std
        higherbound = median + std
        df = pd.DataFrame({'peak':median['peak'], 'lowerbound':lowerbound['peak'], 'higherbound':higherbound['peak']})
        
        stream.send(df)
      
    def push_std(stream):
        
        TS_key = switch_key + '_TS'
        data = list(peak[switch_key])
        timestamp = list(peakTS[TS_key])
       
        times = [1000*time for time in timestamp]
        dataSeries = pd.Series(data, index=times)
        
        zipped = basic_event_builder(peak=dataSeries)
        median = zipped.rolling(120, min_periods=1).median()
        std = zipped.rolling(120, min_periods=1).std()
        lowerbound = median - std
        higherbound = median + std
        df = pd.DataFrame({'lowerbound':lowerbound['peak'], 'higherbound':higherbound['peak']})
        
        stream.send(df)
    
    def push_spikes(stream, position):
        
        #start = [1534279200000, 1534201350000]
        doubledData = [val for val in position for _ in (0, 1)]
        height = [1000, -1000]
        heightList = height*len(position)
        
        df = pd.DataFrame({'location':doubledData, 'y': heightList})
        df = df.set_index('location')
        df.index.name = None
        stream.send(df)

    def push_labels(stream, labels, start):
        
        nonlocal medianCheck

        # Need to clear the buffers somehow to stop weird overlapping
        height = [1]
        data = list(peak[switch_key])
        dataSeries = pd.Series(data)
        median = [dataSeries.median()]

        if median == medianCheck:
            pass
        else:
            
            heightList = median*len(start)
        
            df = pd.DataFrame({'x': start, 'y': heightList, 'labels': labels})
            df = df.set_index('labels')
            df.index.name = None
            with util.disable_constant(s_labels):
                s_labels.data = s_labels.data.iloc[:0]
            stream.send(pd.DataFrame({'x':[], 'y':[]}))
            stream.send(df)
            medianCheck = median
        
    def clear_buffer():
        """
        Modified version of hv.buffer.clear() since original appears to be
        buggy
        
        Clear buffer/graph whenever switch is toggled
        
        """
     
        nonlocal b_th_peak, b_th_peak_std, s_labels
                
        with util.disable_constant(b_th_peak) and util.disable_constant(b_th_peak_std) and util.disable_constant(s_labels):
            
            b_th_peak.data = b_th_peak.data.iloc[:0]
            b_th_peak_std.data = b_th_peak_std.data.iloc[:0]
            s_labels.data = s_labels.data.iloc[:0]
            
        b_th_peak.send(pd.DataFrame({'peak':[], 'lowerbound':[], 'higherbound':[]}))
        b_th_peak_std.send(pd.DataFrame({'peak':[], 'lowerbound':[], 'higherbound':[]}))
        s_labels.send(pd.DataFrame({'x':[], 'y':[]}))
        
    def switch(attr, old, new):
        """
        Update drop down menu value
        
        """
        
        nonlocal switch_key
        switch_key = select.value
        clear_buffer()
        print("Yes!")
    
    def play_graph():
        """
        Provide play and pause functionality to the graph

        """
        
        nonlocal callback_id_th_b, cb_id_spikes, cb_id_labels, cb_id_spikes_end
        if startButton.label == '► Play':
            startButton.label = '❚❚ Pause'
            callback_id_th_b = doc.add_periodic_callback(
                partial(push_data, stream=b_th_peak), 
                1000)
            
            cb_id_spikes = doc.add_periodic_callback(
                partial(push_spikes, 
                        stream=s_spikes, 
                        position=start), 
                1000)

            cb_id_labels = doc.add_periodic_callback(
                partial(push_labels, 
                        stream=s_labels, 
                        labels=labels, 
                        start=start), 
                1000)

            cb_id_spikes_end = doc.add_periodic_callback(
                partial(push_spikes, stream=s_spikes_end, position=end), 1000)
        else:
            startButton.label = '► Play'
            doc.remove_periodic_callback(callback_id_th_b)
    
            doc.remove_periodic_callback(cb_id_spikes)
            doc.remove_periodic_callback(cb_id_labels)
            doc.remove_periodic_callback(cb_id_spikes_end)
        
    select = Select(title="Peak:", value="peak_8", options=list(peak))
    select.on_change('value', switch)
    
    startButton = Button(label='❚❚ Pause')
    startButton.on_click(play_graph)
    
    callback_id_th_b = doc.add_periodic_callback(
        partial(push_data, stream=b_th_peak), 
        1000)

    cb_id_labels = doc.add_periodic_callback(
        partial(push_labels, stream=s_labels, labels=labels, start=start), 
        1000)

    cb_id_spikes = doc.add_periodic_callback(
        partial(push_spikes, stream=s_spikes, position=start),
        1000)

    cb_id_spikes_end = doc.add_periodic_callback(
        partial(push_spikes, stream=s_spikes_end, position=end), 
        1000)
    
    plot = column(select, startButton, hvplot.state)
                           
    doc.title = "Time History Graphs"
    doc.add_root(plot)
    

def new_data(*args, **kwargs):
    """
    Append data from subscribe into data containers
    
    """
    
    kwargs['in_value'].append(kwargs['value'])
    kwargs['in_time'].append(kwargs['timestamp'])

def launch_server():
    '''
    Launch a bokeh_server to plot a hextiles plot of ipm value over ebeam value
    and generate a background contour plot with updating scatter plot on top of it.
    Functionalities include a save button, clear button, pause button, and (buggy) ipm
    select drop down menu for the hextiles plot. Contour and scatter plot have an update
    button and select drop down.
    
    '''
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

    origins = ["localhost:{}".format(5006)]
    
    server = Server(
        {
            '/Time_History': partial(
                produce_timehistory,
                peak=peakDict,
                peakTS=peakTSDict
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
