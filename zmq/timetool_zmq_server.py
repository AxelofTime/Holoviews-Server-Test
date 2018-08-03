import sys
import zmq
import traceback

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
from holoviews.core import util
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


def my_partial(func, *args, **kwargs):
    """
    Modified partial function from functools without type check
    
    Needed for Python 2.7 since 2.7 cannot recognize that hv.Elements
    are callable
    
    """
    
    def wrap(*args, **kwargs):
        return func(*args, **kwargs)
    return partial(wrap, *args, **kwargs)
    
class BokehApp:
    
    def __init__(self):
        self.switchButton = 'ipm2__sum'
        self.maxlen = 1000000
        
        # Initialize buffers
        self.b_timetool = Buffer(pd.DataFrame({'timestamp': [], 'timetool': []}), length=40000)
        self.b_IpmAmp = Buffer(pd.DataFrame({'timetool': [], 'ipm': []}), length=1000)
        self.b_corr_timehistory = Buffer(pd.DataFrame({'timestamp':[],'correlation':[]}), length=40000)
        
        # Initialize callbacks
        self.cb_id_timetool = None
        self.cb_id_amp_ipm = None
        self.cb_id_corr_timehistory = None
                
    def clear_buffer(self):
        """
        Modified version of hv.buffer.clear() since original appears to be
        buggy
        
        Clear buffer/graph whenever switch is toggled
        
        """
        
        data = pd.DataFrame({'timestamp':[], 'correlation':[]})
        
        with util.disable_constant(self.b_corr_timehistory) and util.disable_constant(self.b_IpmAmp):
            
            self.b_IpmAmp.data = self.b_IpmAmp.data.iloc[:0]
            self.b_corr_timehistory.data = self.b_corr_timehistory.data.iloc[:0]
            
        self.b_IpmAmp.send(pd.DataFrame({'timetool': [], 'ipm': []}))
        self.b_corr_timehistory.send(data)
    
    def produce_graphs(self, context, doc):
        """
        Create timetool data timehistory, timetool vs ipm, 
        and correlation timehistory graphs.
        
        Parameters
        ----------
        
        context = zmq.Context()
            Creates zmq socket to receive data
            
        doc: bokeh.document (I think)
            Bokeh document to be displayed on webpage
        
        """

        port = 5006
        socket = context.socket(zmq.SUB)
        
        # MUST BE FROM SAME MACHINE, CHANGE IF NECESSARY!!!
        socket.connect("tcp://psanagpu114:%d" % port)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        
        # Note: Cannot name 'timetool' variables in hvTimeTool and hvIpmAmp the same thing
        # Otherwise, holoviews will try to sync the axis and throw off the ranges for the plots
        # since hvIpmAmp only deals with the last 1000 points whereas hvTimeTool deals with all
        # the points
        hvTimeTool = hv.DynamicMap(
            my_partial(hv.Points, kdims=['timestamp', 'timetool']), streams=[self.b_timetool]).options(
            width=1000, finalize_hooks=[apply_formatter], xrotation=45).redim.label(
            timestamp='Time in UTC', timetool='Timetool Data')
        
        hvIpmAmp = hv.DynamicMap(
            my_partial(hv.Scatter, kdims=['timetool', 'ipm']), streams=[self.b_IpmAmp]).options(
            width=500).redim.label(
            timetool='Last 1000 Timetool Data Points', ipm='Last 1000 Ipm Data Points')
        
        hvCorrTimeHistory = hv.DynamicMap(
            my_partial(hv.Scatter, kdims=['timestamp', 'correlation']), streams=[self.b_corr_timehistory]).options(
            width=500, finalize_hooks=[apply_formatter], xrotation=45).redim.label(
            time='Time in UTC')

        layout = (hvIpmAmp+hvCorrTimeHistory+hvTimeTool).cols(2)
        hvplot = renderer.get_plot(layout)

        def push_data_timetool(buffer):
            """
            Push data to timetool time history graph
            
            """

            timetool_d = deque(maxlen=self.maxlen)
            timetool_t = deque(maxlen=self.maxlen)

            if socket.poll(timeout=0):
                data_dict = socket.recv_pyobj()
                timetool_d = data_dict['tt__FLTPOS_PS']

                # Get time from data_dict
                timeData = deque(maxlen=self.maxlen)
                for time in data_dict['event_time']:
                    num1 = str(time[0])
                    num2 = str(time[1])
                    fullnum = num1 + "." + num2
                    timeData.append(float(fullnum))
                timetool_t = timeData

            # Convert time to seconds so bokeh formatter can get correct datetime
            times = [1000*time for time in list(timetool_t)]

            data = pd.DataFrame({'timestamp': times, 'timetool': timetool_d})
                        
            buffer.send(data)
            
        def push_data_amp_ipm (buffer):
            """
            Push data into timetool amp vs ipm graph
            
            """
        
            timetool_d = deque(maxlen=self.maxlen)
            ipm_d = deque(maxlen=self.maxlen)

            if socket.poll(timeout=0):
                data_dict = socket.recv_pyobj()
                timetool_d = data_dict['tt__AMPL']
                ipm_d = data_dict[self.switchButton]

            data = pd.DataFrame({'timetool': timetool_d, 'ipm': ipm_d})

            buffer.send(data)
            
        def push_data_corr_time_history(buffer):
            """
            Calculate correlation between timetool amp and ipm and
            push to correlation time history graph
            
            """
        
            timetool_d = deque(maxlen=self.maxlen)
            timetool_t = deque(maxlen=self.maxlen)
            ipm_d = deque(maxlen=self.maxlen)

            if socket.poll(timeout=0):
                data_dict = socket.recv_pyobj()
                timetool_d = data_dict['tt__FLTPOS_PS']
                ipm_d = data_dict[self.switchButton]

                # Get time from data_dict
                timeData = deque(maxlen=self.maxlen)
                for time in data_dict['event_time']:
                    num1 = str(time[0])
                    num2 = str(time[1])
                    fullnum = num1 + "." + num2
                    timeData.append(float(fullnum))
                timetool_t = timeData

            # Convert time to seconds so bokeh formatter can get correct datetime
            times = [1000*time for time in list(timetool_t)]

            data = pd.DataFrame({'timetool': timetool_d, 'ipm': ipm_d})
            data_corr = data['timetool'].rolling(window=120).corr(other=data['ipm'])

            # Start at index 119 so we don't get null data
            final_df = pd.DataFrame({
                'timestamp': times[119:], 
                'correlation': data_corr[119:]
            })

            buffer.send(final_df)
                    
        def switch(attr, old, new):
            """
            Update drop down menu value

            """
            
            self.switchButton = select.value
            self.clear_buffer()
        
        def stop():
            """
            Add pause and play functionality to graph
            
            """
            
            if stopButton.label == 'Play':
                stopButton.label = 'Pause'
                self.cb_id_timetool = doc.add_periodic_callback(
                    partial(push_data_timetool, 
                            buffer=self.b_timetool), 
                    1000)

                self.cb_id_amp_ipm = doc.add_periodic_callback(
                    partial(push_data_amp_ipm,
                            buffer=self.b_IpmAmp), 
                    1000)

                self.cb_id_corr_timehistory = doc.add_periodic_callback(
                    partial(push_data_corr_time_history, 
                            buffer=self.b_corr_timehistory), 
                    1000)
            else:
                stopButton.label = 'Play'
                doc.remove_periodic_callback(self.cb_id_timetool)
                doc.remove_periodic_callback(self.cb_id_amp_ipm)
                doc.remove_periodic_callback(self.cb_id_corr_timehistory)
        
        # Start the callback
        self.cb_id_timetool = doc.add_periodic_callback(
            partial(push_data_timetool, 
                    buffer=self.b_timetool), 
            1000)

        self.cb_id_amp_ipm = doc.add_periodic_callback(
            partial(push_data_amp_ipm,
                    buffer=self.b_IpmAmp), 
            1000)

        self.cb_id_corr_timehistory = doc.add_periodic_callback(
            partial(push_data_corr_time_history, 
                    buffer=self.b_corr_timehistory), 
            1000)
        
        # Use this to test since ipm2 and ipm3 are too similar to see any differences
        # select = Select(title='ipm value:', value='ipm2__sum', options=['ipm2__sum', 'tt__FLTPOS_PS'])
        select = Select(title='ipm value:', value='ipm2__sum', options=['ipm2__sum', 'ipm3__sum'])
        select.on_change('value', switch) 
        
        stopButton = Button(label='Pause')
        stopButton.on_click(stop)
        
        plot = column(select, stopButton, hvplot.state)
        doc.add_root(plot)
        
def make_document(context, doc):
    """
    Create an instance of BokehApp() for each instance of the server
    
    """
    
    bokehApp = BokehApp()
    
    bokehApp.produce_graphs(context, doc)
    
def launch_server():
    """
    Launch a bokeh_server to plot the a timetool time history, timetool amp
    vs ipm, and correlation graph by using zmq to get the data.
    
    """
   
    context = zmq.Context()

    origins = ["localhost:{}".format(5000)]
    
    apps = {'/': Application(FunctionHandler(partial(make_document, context)))}
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
