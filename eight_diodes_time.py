import numpy as np
import holoviews as hv
import pandas as pd

import sys
from bokeh.layouts import layout, widgetbox, row
from bokeh.models import Button, Slider, Select, HoverTool
from bokeh.plotting import curdoc
from bokeh.io import output_file, save
from bokeh.server.server import Server
from bokeh.application import Application
from holoviews.streams import Pipe, Buffer
import tables
from eight_diodes_beam import FakeEightBeams
from functools import partial
from collections import deque
from event_builder import basic_event_builder
import time
from bokeh.models import DatetimeTickFormatter


renderer = hv.renderer('bokeh').instance(mode='server')

def apply_formatter(plot, element):
    plot.handles['xaxis'].formatter = DatetimeTickFormatter()

def produce_curve(doc, diode_t, diode):
    
    # Stream
    
    #buffer = Buffer(pd.DataFrame({'diode_t':[],'diode':[]}), length=100)
    buffer = Buffer(pd.DataFrame({'diode':[]}), length=100)

    
    # Weird bug where if you leave the beginning of the graph in buffer zone, there will be lines connecting to beginning
    
    # Generate dynamic map
    hvCurve = hv.DynamicMap(hv.Curve, streams=[buffer]).options(
        width=1000, finalize_hooks=[apply_formatter])
    #hvCurve = hv.DynamicMap(partial(hv.Curve, kdims=['diode_t','diode']), streams=[buffer]).options(
    #    width=1000, finalize_hooks=[apply_formatter])
    
    hvplot = renderer.get_plot(hvCurve, doc)
    
    callback_id = None
    
    def push_data():
        
        # Couldn't get the axis labels to be in datetime.
        
        #timeStuff = pd.to_datetime(diode_t)
        #print(timeStuff)
        #goog_dates = np.array(GOOG['date'], dtype=np.datetime64)
        #print(diode_t)
        #times = np.array(diode_t, dtype=np.datetime64)
        #print(times)
        timeStuff = list(diode_t)
        times = pd.to_datetime(timeStuff, unit='s')
        times = times.tz_localize('UTC').tz_convert('US/Pacific')
        
        #testing = pd.DataFrame({'diode_t':times, 'diode':list(diode)})
        
        diodeData = pd.Series(diode, index=diode_t)
        #time2 = pd.Series(diode_t, index=diode_t)
        #zipped = basic_event_builder(diode_t=time2, diode=diodeData)
        zipped = basic_event_builder(diode=diodeData)
        buffer.send(zipped)
        #streamCurve.event(df=zipped)
        #print(zipped)
        
    callback_id = doc.add_periodic_callback(push_data, 200)
    
    plot = layout([hvplot.state])
    doc.add_root(plot)

def new_data(*args, **kwargs):
    
    kwargs['in_value'].append(kwargs['value'])
    kwargs['in_time'].append(kwargs['timestamp'])

def launch_server():
    
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
    
    # I could probably put this in a forloop later...
    beam.fake_dcc.subscribe(
        partial(new_data, in_value=dcc_d, in_time=dcc_t)
    )
    
#     beam.fake_dci.subscribe(
#         partial(new_data, in_value=dci_d, in_time=dci_t)
#     )
    
#     beam.fake_dco.subscribe(
#         partial(new_data, in_value=dco_d, in_time=dco_t)
#     )
    
#     beam.fake_dd.subscribe(
#         partial(new_data, in_value=dd_d, in_time=dd_t)
#     )
    
#     beam.fake_di.subscribe(
#         partial(new_data, in_value=di_d, in_time=di_t)
#     )
    
#     beam.fake_do.subscribe(
#         partial(new_data, in_value=do_d, in_time=do_t)
#     )
    
#     beam.fake_t1d.subscribe(
#         partial(new_data, in_value=t1d_d, in_time=t1d_t)
#     )
    
#     beam.fake_t4d.subscribe(
#         partial(new_data, in_value=t4d_d, in_time=t4d_t)
#     )

    origins = ["localhost:{}".format(5006)]
    
    server = Server(
        {
            '/Testing': partial(
                produce_curve,
                diode_t=dcc_t,
                diode=dcc_d
            )
        },
        allow_websocket_origin=origins,
        # num_procs must be 1 for tornado loops to work correctly 
        num_procs=1,
    )
    server.start()
    
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        print("terminating")
        server.io_loop.stop()
        
if __name__ == '__main__':
    launch_server()