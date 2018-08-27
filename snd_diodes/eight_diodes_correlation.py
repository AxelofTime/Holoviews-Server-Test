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
    
def produce_correlation_graphs(doc, diode_t_dict, diode_dict):
    """
    Produce correlation graphs and push them onto the web page document.
    
    Parameters
    ----------
    
    doc: bokeh.document (I think)
        Bokeh document to be displayed on webpage
    
    diode_t_dict: dictionary
        diciontary with deques containing timestamps of the diode readings
    
    diode_dict: dictionary
        dictionary with deques containing diode readins
    
    """
    
    # Initialize formatting variables
    buffer_length = 40000
    width = 500
    
    # Initialize Streams
    b_dcc_dco = Buffer(pd.DataFrame({'x_diode':[], 'y_diode':[]}), length=buffer_length)
    b_t4d_dd = Buffer(pd.DataFrame({'x_diode':[], 'y_diode':[]}), length=buffer_length)
    b_do_di = Buffer(pd.DataFrame({'x_diode':[], 'y_diode':[]}), length=buffer_length)
    b_t4d_dco = Buffer(pd.DataFrame({'x_diode':[], 'y_diode':[]}), length=buffer_length)
    
    # Initialize dynamic maps
    hvPoint_dcc_dco = hv.DynamicMap(
        partial(hv.Scatter, kdims=['x_diode','y_diode'], group='DCC vs DCO'), streams=[b_dcc_dco]).options(
        width=width).redim.label(x_diode='DCC', y_diode='DCO')
    
    hvPoint_t4d_dd = hv.DynamicMap(
        partial(hv.Scatter, kdims=['x_diode','y_diode'], group='T4D vs DD'), streams=[b_t4d_dd]).options(
        width=width).redim.label(x_diode='T4D', y_diode='DD')
    
    hvPoint_do_di = hv.DynamicMap(
        partial(hv.Scatter, kdims=['x_diode','y_diode'], group='DO vs DI'), streams=[b_do_di]).options(
        width=width).redim.label(x_diode='DO', y_diode='DI')
    
    hvPoint_t4d_dco = hv.DynamicMap(
        partial(hv.Scatter, kdims=['x_diode','y_diode'], group='T4D vs DCO'), streams=[b_t4d_dco]).options(
        width=width).redim.label(x_diode='T4D', y_diode='DCO')
    
    plots_col = (hvPoint_dcc_dco + hvPoint_t4d_dco + hvPoint_do_di + hvPoint_t4d_dd).cols(2)
    
    # Render plot with bokeh
    hvplot = renderer.get_plot(plots_col, doc)
    
    # Initialize callbacks
    cb_id_dcc_dco = None
    cb_id_t4d_dd = None
    cb_id_do_di = None
    cb_id_t4d_dco = None
    
    # Push data into buffers
    def push_data(x_diode, y_diode, x_diode_t, y_diode_t, buffer):
        """
        Push data from x and y diode into buffer to be graphed.

        """
        
        x_diode_data = pd.Series(x_diode, index=x_diode_t)
        y_diode_data = pd.Series(y_diode, index=y_diode_t)
        zipped = basic_event_builder(x_diode=x_diode_data, y_diode=y_diode_data)
        buffer.send(zipped)
    
    #
    def play_graph():
        """
        Provide play and pause functionality to the graph

        """
        
        nonlocal cb_id_dcc_dco, cb_id_t4d_dd, cb_id_do_di, cb_id_t4d_dco
        
        cb_time = 1000
        
        if startButton.label == '► Play':
            startButton.label = '❚❚ Pause'
            
            cb_id_dcc_dco = doc.add_periodic_callback(
                partial(push_data, x_diode=diode_dict['dcc_d'], y_diode=diode_dict['dco_d'], 
                        x_diode_t=diode_t_dict['dcc_t'], y_diode_t=diode_t_dict['dco_t'], buffer=b_dcc_dco),
                cb_time)

            cb_id_t4d_dd = doc.add_periodic_callback(
                partial(push_data, x_diode=diode_dict['t4d_d'], y_diode=diode_dict['dd_d'], 
                        x_diode_t=diode_t_dict['t4d_t'], y_diode_t=diode_t_dict['dd_t'], buffer=b_t4d_dd),
                cb_time)

            cb_id_do_di = doc.add_periodic_callback(
                partial(push_data, x_diode=diode_dict['do_d'], y_diode=diode_dict['di_d'], 
                        x_diode_t=diode_t_dict['do_t'], y_diode_t=diode_t_dict['di_t'], buffer=b_do_di),
                cb_time)

            cb_id_t4d_dco = doc.add_periodic_callback(
                partial(push_data, x_diode=diode_dict['t4d_d'], y_diode=diode_dict['dco_d'], 
                        x_diode_t=diode_t_dict['t4d_t'], y_diode_t=diode_t_dict['dco_t'], buffer=b_t4d_dco),
                cb_time)
            
        else:
            startButton.label = '► Play'
            doc.remove_periodic_callback(cb_id_dcc_dco)
            doc.remove_periodic_callback(cb_id_t4d_dd)
            doc.remove_periodic_callback(cb_id_do_di)
            doc.remove_periodic_callback(cb_id_t4d_dco)
    
    # Create widgets
    startButton = Button(label='► Play')
    startButton.on_click(play_graph)
    
    plot = layout([startButton, row([hvplot.state])])
    
    doc.title = "Correlation Graphs"
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
            '/Correlation': partial(
                produce_correlation_graphs,
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