import numpy as np
import holoviews as hv
import pandas as pd

import sys
from bokeh.layouts import layout, widgetbox, row
from bokeh.models import Button, Slider, Select, HoverTool, DatetimeTickFormatter
from bokeh.plotting import curdoc
from bokeh.io import output_file, save
from bokeh.server.server import Server
from bokeh.application import Application
from holoviews.streams import Buffer
import tables
from eight_diodes_beam import FakeEightBeams
from functools import partial
from collections import deque
from event_builder import basic_event_builder
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


def produce_curve(doc, diode_t_dict, diode_dict):
    """
    Produce time history graphs and push them onto the web page document.
    
    Parameters
    ----------
    
    doc: bokeh.document (I think)
        Bokeh document to be displayed on webpage
    
    diode_t_dict: dictionary
        diciontary with deques containing timestamps of the diode readings
    
    diode_dict: dictionary
        dictionary with deques containing diode readings
    
    """
                      
    # Initialize formatting variables
    buffer_length = 40000
    width = 500
    xrotation = 45
    transparent_line_value = 0.1
    
    # Initialize streams
    buffer_dcc = Buffer(pd.DataFrame({'diode':[]}), length=buffer_length)
    buffer_dci = Buffer(pd.DataFrame({'diode':[]}), length=buffer_length)
    buffer_dco = Buffer(pd.DataFrame({'diode':[]}), length=buffer_length)
    buffer_dd = Buffer(pd.DataFrame({'diode':[]}), length=buffer_length)
    buffer_di = Buffer(pd.DataFrame({'diode':[]}), length=buffer_length)
    buffer_do = Buffer(pd.DataFrame({'diode':[]}), length=buffer_length)
    buffer_t1d = Buffer(pd.DataFrame({'diode':[]}), length=buffer_length)
    buffer_t4d = Buffer(pd.DataFrame({'diode':[]}), length=buffer_length)
        
    b_dcc_std = Buffer(pd.DataFrame({'lowerbound':[], 'higherbound':[]}), length=buffer_length)
    b_dci_std = Buffer(pd.DataFrame({'lowerbound':[], 'higherbound':[]}), length=buffer_length)
    b_dco_std = Buffer(pd.DataFrame({'lowerbound':[], 'higherbound':[]}), length=buffer_length)
    b_dd_std = Buffer(pd.DataFrame({'lowerbound':[], 'higherbound':[]}), length=buffer_length)
    b_di_std = Buffer(pd.DataFrame({'lowerbound':[], 'higherbound':[]}), length=buffer_length)
    b_do_std = Buffer(pd.DataFrame({'lowerbound':[], 'higherbound':[]}), length=buffer_length)
    b_t1d_std = Buffer(pd.DataFrame({'lowerbound':[], 'higherbound':[]}), length=buffer_length)
    b_t4d_std = Buffer(pd.DataFrame({'lowerbound':[], 'higherbound':[]}), length=buffer_length)

    # Weird bug where if you leave the beginning of the Curve graph in buffer zone, 
    # there will be lines connecting to beginning
    
    # Generate dynamic map for medians
    hvPoint_dcc = hv.DynamicMap(
        partial(hv.Points, group='Diode', label='DCC'), streams=[buffer_dcc]).options(
        width=width, finalize_hooks=[apply_formatter], xrotation=xrotation).redim.label(
        index='Time in UTC', diode='DCC Reading')
    
    hvPoint_dci = hv.DynamicMap(
        partial(hv.Points, group='Diode', label='DCI'), streams=[buffer_dci]).options(
        width=width, finalize_hooks=[apply_formatter], xrotation=xrotation).redim.label(
        index='Time in UTC', diode='DCI Reading')
    
    hvPoint_dco = hv.DynamicMap(
        partial(hv.Points, group='Diode', label='DCO'), streams=[buffer_dco]).options(
        width=width, finalize_hooks=[apply_formatter], xrotation=xrotation).redim.label(
        index='Time in UTC', diode='DCO Reading')
    
    hvPoint_dd = hv.DynamicMap(
        partial(hv.Points, group='Diode', label='DD'), streams=[buffer_dd]).options(
        width=width, finalize_hooks=[apply_formatter], xrotation=xrotation).redim.label(
        index='Time in UTC', diode='DD Reading')
    
    hvPoint_di = hv.DynamicMap(
        partial(hv.Points, group='Diode', label='DI'), streams=[buffer_di]).options(
        width=width, finalize_hooks=[apply_formatter], xrotation=xrotation).redim.label(
        index='Time in UTC', diode='DI Reading')
    
    hvPoint_do = hv.DynamicMap(
        partial(hv.Points, group='Diode', label='DO'), streams=[buffer_do]).options(
        width=width, finalize_hooks=[apply_formatter], xrotation=xrotation).redim.label(
        index='Time in UTC', diode='DO Reading')
    
    hvPoint_t1d = hv.DynamicMap(
        partial(hv.Points, group='Diode', label='T1D'), streams=[buffer_t1d]).options(
        width=width, finalize_hooks=[apply_formatter], xrotation=xrotation).redim.label(
        index='Time in UTC', diode='T1D Reading')
    
    hvPoint_t4d = hv.DynamicMap(
        partial(hv.Points, group='Diode', label='T4D'), streams=[buffer_t4d]).options(
        width=width, finalize_hooks=[apply_formatter], xrotation=xrotation).redim.label(
        index='Time in UTC', diode='T4D Reading')
    
    # Same bug with weird connecting lines, but doesn't happen for std Curve graphs (happens for Area graphs)
    
    # Generate dynamic map for standard deviation
    hvStd_dcc_low = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'lowerbound']), streams=[b_dcc_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_dcc_high = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'higherbound']), streams=[b_dcc_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_dci_low = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'lowerbound']), streams=[b_dci_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_dci_high = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'higherbound']), streams=[b_dci_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_dco_low = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'lowerbound']), streams=[b_dco_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_dco_high = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'higherbound']), streams=[b_dco_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_dd_low = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'lowerbound']), streams=[b_dd_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_dd_high = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'higherbound']), streams=[b_dd_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_di_low = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'lowerbound']), streams=[b_di_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_di_high = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'higherbound']), streams=[b_di_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_do_low = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'lowerbound']), streams=[b_do_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_do_high = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'higherbound']), streams=[b_do_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_t1d_low = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'lowerbound']), streams=[b_t1d_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_t1d_high = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'higherbound']), streams=[b_t1d_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_t4d_low = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'lowerbound']), streams=[b_t4d_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
    hvStd_t4d_high = hv.DynamicMap(partial(
        hv.Curve, kdims=['index', 'higherbound']), streams=[b_t4d_std]).options(
        width=width, line_alpha=transparent_line_value, line_color='red').redim.label(
        index='Time in UTC')
    
#     Ideally, we would have wanted to plot the standard deviations as an area curve
#     I didn't do it beceause there's a bug, but this would theoretically be the code
#     to make a dynamic map with hv.Area
    
#     hvArea = hv.DynamicMap(partial(
#         hv.Area, vdims=['lowerbound', 'higherbound']), streams=[buffer_std_test]).options(
#         width=1000).redim.label(index='Time in UTC')
    
    # Put plots into two columns in layout
    plots = (hvPoint_dcc*hvStd_dcc_low*hvStd_dcc_high
             + hvPoint_dci*hvStd_dci_low*hvStd_dci_high
             + hvPoint_dco*hvStd_dco_low*hvStd_dco_high
             + hvPoint_dd*hvStd_dd_low*hvStd_dd_high
             + hvPoint_di*hvStd_di_low*hvStd_di_high
             + hvPoint_do*hvStd_do_low*hvStd_do_high
             + hvPoint_t1d*hvStd_t1d_low*hvStd_t1d_high
             + hvPoint_t4d*hvStd_t4d_low*hvStd_t4d_high).cols(2)
    
    # Use bokeh to render the plot
    hvplot = renderer.get_plot(plots, doc)
    
    # Initialize callbacks
    cb_id_dcc = None
    cb_id_dci = None
    cb_id_dco = None
    cb_id_dd = None
    cb_id_di = None
    cb_id_do = None
    cb_id_t1d = None
    cb_id_t4d = None
    
    cb_id_dcc_std = None
    cb_id_dci_std = None
    cb_id_dco_std = None
    cb_id_dd_std = None
    cb_id_di_std = None
    cb_id_do_std = None
    cb_id_t1d_std = None
    cb_id_t4d_std = None
        
    def push_data_median(diode_t, diode, buffer):
        """
        Push rolling median of diode readings and push resulting list into buffer
        to be graphed.

        """
                
        timeStuff = list(diode_t)
        # Convert time to seconds so bokeh formatter can get correct datetime
        times = [1000*time for time in timeStuff]
       
        diodeData = pd.Series(diode, index=times)
     
        zipped = basic_event_builder(diode=diodeData)
        median = zipped.rolling(120, min_periods=1).median()
        # Exclude first 119 points because of binning issues and sparsing the data (Doesn't seem to really work though)
        buffer.send(median[119::2])
        zipped.to_csv('testData2.csv')
        
    def push_data_std(diode_t, diode, buffer):
        """
        Calculate rolling standard deviation of diode readings. Generate lists
        containing values one standard deviation away from the median (lower and higher)
        and push resulting list into buffer to be graphed.

        """
        
        timeStuff = list(diode_t)
        times = [1000*time for time in timeStuff] # Convert time to seconds so bokeh formatter can get correct datetime
        
        diodeData = pd.Series(diode, index=times)
        zipped = basic_event_builder(diode=diodeData)
        
        median = zipped.rolling(120, min_periods=1).median()
        std = zipped.rolling(120, min_periods=1).std()
        lowerbound = median - std
        higherbound = median + std
        df = pd.DataFrame({'lowerbound':lowerbound['diode'], 'higherbound':higherbound['diode']})
        buffer.send(df[119::2])
    
    
    def play_graph():
        """
        Provide play and pause functionality to the graph

        """
        
        nonlocal cb_id_dcc, cb_id_dci, cb_id_dco, cb_id_dd, cb_id_di, cb_id_do, cb_id_t1d, cb_id_t4d
        nonlocal cb_id_dcc_std, cb_id_dci_std, cb_id_dco_std, cb_id_dd_std 
        nonlocal cb_id_di_std, cb_id_do_std, cb_id_t1d_std, cb_id_t4d_std
        
        if startButton.label == '► Play':
            startButton.label = '❚❚ Pause'
            
            cb_time = 3000
            
            # Callbacks for median lines
            cb_id_dcc = doc.add_periodic_callback(
                partial(push_data_median, diode_t=diode_t_dict['dcc_t'], 
                        diode=diode_dict['dcc_d'], buffer=buffer_dcc), 
                cb_time)

            cb_id_dci = doc.add_periodic_callback(
                partial(push_data_median, diode_t=diode_t_dict['dci_t'], 
                        diode=diode_dict['dci_d'], buffer=buffer_dci), 
                cb_time)

            cb_id_dco = doc.add_periodic_callback(
                partial(push_data_median, diode_t=diode_t_dict['dco_t'], 
                        diode=diode_dict['dco_d'], buffer=buffer_dco), 
                cb_time)

            cb_id_dd = doc.add_periodic_callback(
                partial(push_data_median, diode_t=diode_t_dict['dd_t'], 
                        diode=diode_dict['dd_d'], buffer=buffer_dd), 
                cb_time)

            cb_id_di = doc.add_periodic_callback(
                partial(push_data_median, diode_t=diode_t_dict['di_t'], 
                        diode=diode_dict['di_d'], buffer=buffer_di), 
                cb_time)

            cb_id_do = doc.add_periodic_callback(
                partial(push_data_median, diode_t=diode_t_dict['do_t'], 
                        diode=diode_dict['do_d'], buffer=buffer_do), 
                cb_time)

            cb_id_t1d = doc.add_periodic_callback(
                partial(push_data_median, diode_t=diode_t_dict['t1d_t'], 
                        diode=diode_dict['t1d_d'], buffer=buffer_t1d), 
                cb_time)

            cb_id_t4d = doc.add_periodic_callback(
                partial(push_data_median, diode_t=diode_t_dict['t4d_t'], 
                        diode=diode_dict['t4d_d'], buffer=buffer_t4d), 
                cb_time)
            
            # Callbacks for std lines
            cb_id_dcc_std = doc.add_periodic_callback(
                partial(push_data_std, diode_t=diode_t_dict['dcc_t'], 
                        diode=diode_dict['dcc_d'], buffer=b_dcc_std), 
                cb_time)
            cb_id_dci_std = doc.add_periodic_callback(
                partial(push_data_std, diode_t=diode_t_dict['dci_t'], 
                        diode=diode_dict['dci_d'], buffer=b_dci_std), 
                cb_time)
            cb_id_dco_std = doc.add_periodic_callback(
                partial(push_data_std, diode_t=diode_t_dict['dco_t'], 
                        diode=diode_dict['dco_d'], buffer=b_dco_std), 
                cb_time)
            cb_id_dd_std = doc.add_periodic_callback(
                partial(push_data_std, diode_t=diode_t_dict['dd_t'], 
                        diode=diode_dict['dd_d'], buffer=b_dd_std), 
                cb_time)
            cb_id_di_std = doc.add_periodic_callback(
                partial(push_data_std, diode_t=diode_t_dict['di_t'], 
                        diode=diode_dict['di_d'], buffer=b_di_std), 
                cb_time)
            cb_id_do_std = doc.add_periodic_callback(
                partial(push_data_std, diode_t=diode_t_dict['do_t'], 
                        diode=diode_dict['do_d'], buffer=b_do_std), 
                cb_time)
            cb_id_t1d_std = doc.add_periodic_callback(
                partial(push_data_std, diode_t=diode_t_dict['t1d_t'], 
                        diode=diode_dict['t1d_d'], buffer=b_t1d_std), 
                cb_time)
            cb_id_t4d_std = doc.add_periodic_callback(
                partial(push_data_std, diode_t=diode_t_dict['t4d_t'], 
                        diode=diode_dict['t4d_d'], buffer=b_t4d_std), 
                cb_time)
        else:
            startButton.label = '► Play'
            doc.remove_periodic_callback(cb_id_dcc)
            doc.remove_periodic_callback(cb_id_dci)
            doc.remove_periodic_callback(cb_id_dco)
            doc.remove_periodic_callback(cb_id_dd)
            doc.remove_periodic_callback(cb_id_di)
            doc.remove_periodic_callback(cb_id_do)
            doc.remove_periodic_callback(cb_id_t1d)
            doc.remove_periodic_callback(cb_id_t4d)
            
            doc.remove_periodic_callback(cb_id_dcc_std)
            doc.remove_periodic_callback(cb_id_dci_std)
            doc.remove_periodic_callback(cb_id_dco_std)
            doc.remove_periodic_callback(cb_id_dd_std)
            doc.remove_periodic_callback(cb_id_di_std)
            doc.remove_periodic_callback(cb_id_do_std)
            doc.remove_periodic_callback(cb_id_t1d_std)
            doc.remove_periodic_callback(cb_id_t4d_std)
    
    # Create widgets
    startButton = Button(label='► Play')
    startButton.on_click(play_graph)
    
    plot = layout([startButton, hvplot.state])
    doc.title = "Time History"
    doc.add_root(plot)

def new_data(*args, **kwargs):
    """
    Append data from subscribe into data containers
    
    """
    
    kwargs['in_value'].append(kwargs['value'])
    kwargs['in_time'].append(kwargs['timestamp'])
    #print("I'm working!")

def launch_server():
    '''
    Launch a bokeh_server to plot the time history of dcc, dci, dco, 
    dd, di, do, t1d, and t4d diodes and the correlation graphs between 
    dcc and dco, t4d and dd, do and di, and t4d and dco.
    
    '''
    
    maxlen = 1000000
    
    # Initialize data carriers
    beam = FakeEightBeams()

    dcc_d = deque(maxlen=maxlen)
    dci_d = deque(maxlen=maxlen)
    dco_d = deque(maxlen=maxlen)
    dd_d = deque(maxlen=maxlen)
    di_d = deque(maxlen=maxlen)
    do_d = deque(maxlen=maxlen)
    t1d_d = deque(maxlen=maxlen)
    t4d_d = deque(maxlen=maxlen)
    
    dcc_t = deque(maxlen=maxlen)
    dci_t = deque(maxlen=maxlen)
    dco_t = deque(maxlen=maxlen)
    dd_t = deque(maxlen=maxlen)
    di_t = deque(maxlen=maxlen)
    do_t = deque(maxlen=maxlen)
    t1d_t = deque(maxlen=maxlen)
    t4d_t = deque(maxlen=maxlen)
    
    diode_dict = {'dcc_d':dcc_d, 'dci_d':dci_d, 
                  'dco_d':dco_d, 'dd_d':dd_d, 
                  'di_d':di_d, 'do_d':do_d, 
                  't1d_d':t1d_d, 't4d_d':t4d_d}
    
    diode_t_dict = {'dcc_t':dcc_t, 'dci_t':dci_t,
                    'dco_t':dco_t, 'dd_t':dd_t, 
                    'di_t':di_t, 'do_t':do_t, 
                    't1d_t':t1d_t, 't4d_t':t4d_t}
    
    # Subscribe to diodes
    beam.fake_dcc.subscribe(
        partial(new_data, in_value=dcc_d, in_time=dcc_t)
    )
    
    beam.fake_dci.subscribe(
        partial(new_data, in_value=dci_d, in_time=dci_t)
    )
    
    beam.fake_dco.subscribe(
        partial(new_data, in_value=dco_d, in_time=dco_t)
    )
    
    beam.fake_dd.subscribe(
        partial(new_data, in_value=dd_d, in_time=dd_t)
    )
    
    beam.fake_di.subscribe(
        partial(new_data, in_value=di_d, in_time=di_t)
    )
    
    beam.fake_do.subscribe(
        partial(new_data, in_value=do_d, in_time=do_t)
    )
    
    beam.fake_t1d.subscribe(
        partial(new_data, in_value=t1d_d, in_time=t1d_t)
    )
    
    beam.fake_t4d.subscribe(
        partial(new_data, in_value=t4d_d, in_time=t4d_t)
    )

    origins = ["localhost:{}".format(5006)]
    
    server = Server(
        {
            '/Time_History': partial(
                produce_curve,
                diode_t_dict=diode_t_dict,
                diode_dict=diode_dict
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