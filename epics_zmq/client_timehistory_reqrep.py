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
from holoviews.core import util
from event_builder import basic_event_builder
import tables
from functools import partial
from collections import deque
import datetime
from holoviews.operation.datashader import datashade, dynspread
from holoviews.operation import decimate

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

class BokehApp:
    
    def __init__(self):
        self.switch_key = 'peak_8'
        self.maxlen = 1000000
        
        # Initialize buffers
        self.b_th_peak = Buffer(pd.DataFrame({'peak':[], 'lowerbound':[], 'higherbound':[]}), length=1000000)
        
        # Initialize callbacks
        self.callback_id_th_b = None
        
    def clear_buffer(self):
        """
        Modified version of hv.buffer.clear() since original appears to be
        buggy

        Clear buffer/graph whenever switch is toggled

        """
        with util.disable_constant(self.b_th_peak):

            self.b_th_peak.data = self.b_th_peak.data.iloc[:0]

        self.b_th_peak.send(pd.DataFrame({'peak':[], 'lowerbound':[], 'higherbound':[]}))
    
    def produce_timehistory(self, context, doc):
        """
        Create timetool data timehistory
        
        Parameters
        ----------
        
        context = zmq.Context()
            Creates zmq socket to receive data
            
        doc: bokeh.document (I think)
            Bokeh document to be displayed on webpage
        
        """

        # Port to connect to master
        port = 5000
        socket = context.socket(zmq.REQ)
        
        # MUST BE FROM SAME MACHINE, CHANGE IF NECESSARY!!!
        socket.connect("tcp://localhost:%d" % port)
        
        # Dynamic Maps
        plot_peak_b = hv.DynamicMap(partial(
            hv.Curve, kdims=['index', 'peak']), streams=[self.b_th_peak]).options(
            width=1000, finalize_hooks=[apply_formatter]).redim.label(
            index='Time in UTC')

        plot_peak_std_low = hv.DynamicMap(partial(
            hv.Curve, kdims=['index', 'lowerbound']), streams=[self.b_th_peak]).options(
            line_alpha=0.5, width=1000, line_color='gray', finalize_hooks=[apply_formatter]).redim.label(
            index='Time in UTC')

        plot_peak_std_high = hv.DynamicMap(partial(
            hv.Curve, kdims=['index', 'higherbound']), streams=[self.b_th_peak]).options(
            line_alpha=0.5, width=1000, line_color='gray').redim.label(
            index='Time in UTC')
        
        # Decimate and datashade
        pointTest = decimate(plot_peak_b, streams=[hv.streams.PlotSize])
        
        test1 = datashade(plot_peak_std_low, streams=[hv.streams.PlotSize], normalization='linear').options(
            width=1000, finalize_hooks=[apply_formatter])
        
        test2 = datashade(plot_peak_std_high, streams=[hv.streams.PlotSize], normalization='linear')
       
        plot = (test1*test2*pointTest)

        # Use bokeh to render plot
        hvplot = renderer.get_plot(plot, doc)

        def push_data(stream):
            
            """
            Push data to timetool time history graph
            
            """
            
            median = pd.DataFrame({'peak':[]})
            lowerbound = pd.DataFrame({'peak':[]})
            higherbound = pd.DataFrame({'peak':[]})
            
            # Request
            socket.send_string("Hello")
            print("Oof")
            
            data_dict = socket.recv_pyobj()
            peakDict = data_dict['peakDict']
            peakTSDict = data_dict['peakTSDict']

            TS_key = self.switch_key + '_TS'
            data = list(peakDict[self.switch_key])
            timestamp = list(peakTSDict[TS_key])

            times = [1000*time for time in timestamp]
            dataSeries = pd.Series(data, index=times)

            zipped = basic_event_builder(peak=dataSeries)
            median = zipped.rolling(120, min_periods=1).median()
            std = zipped.rolling(120, min_periods=1).std()
            lowerbound = median - std
            higherbound = median + std
                            
            df = pd.DataFrame({
                'peak':median['peak'], 
                'lowerbound':lowerbound['peak'], 
                'higherbound':higherbound['peak']
            })

            stream.send(df)

        def switch(attr, old, new):
            """
            Update drop down menu value

            """
            self.switch_key = select.value
            self.clear_buffer()
            print("Yes!")

        def play_graph():
            """
            Provide play and pause functionality to the graph

            """

            if startButton.label == '► Play':
                startButton.label = '❚❚ Pause'
                
                self.callback_id_th_b = doc.add_periodic_callback(
                    partial(push_data, stream=self.b_th_peak), 
                    1000)

            else:
                startButton.label = '► Play'
                doc.remove_periodic_callback(self.callback_id_th_b)

        peak_list = ['peak_8', 'peak_9', 'peak_10', 'peak_11', 'peak_12', 'peak_13', 'peak_14', 'peak_15']
        select = Select(title='Peak:', value='peak_8', options=peak_list)
        select.on_change('value', switch)

        startButton = Button(label='❚❚ Pause')
        startButton.on_click(play_graph)

        self.callback_id_th_b = doc.add_periodic_callback(
            partial(push_data, stream=self.b_th_peak), 
            1000)

        plot = column(select, startButton, hvplot.state)

        doc.title = "Time History Graphs"
        doc.add_root(plot)
    
    
def make_document(context, doc):
    """
    Create an instance of BokehApp() for each instance of the server
    
    """
    
    bokehApp = BokehApp()
    
    bokehApp.produce_timehistory(context, doc)
    
def launch_server():
   
    context = zmq.Context()

    origins = ["localhost:{}".format(5006)]
    
    apps = {'/': Application(FunctionHandler(partial(make_document, context)))}
    server = Server(apps, port=5006)
    
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
