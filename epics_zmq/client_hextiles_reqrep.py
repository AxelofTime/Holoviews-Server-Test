import sys
import zmq
import tables
import datetime

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
from holoviews.operation.datashader import datashade, dynspread
from holoviews.operation import decimate

from event_builder import basic_event_builder
from functools import partial
from collections import deque

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

def gen_hex(df):
    """
    Return holoviews HexTiles plot
    
    Parameters
    ----------
    
    df: pandas.DataFrame
        DataFrame containing data to be ploted on hextiles plot
    
    """
    
    # Get bounds for graph
    colNames = list(df)
    lowX = df[colNames[0]].quantile(0.01)
    highX = df[colNames[0]].quantile(0.99)
    lowY = df[colNames[1]].quantile(0.01)
    highY = df[colNames[1]].quantile(0.99)
    
    return hv.HexTiles(df, group="Number of events: " + str(len(df.index))).redim.range(
        ebeam=(lowX, highX), 
        ipm2 = (lowY, highY)).opts(
        norm=dict(framewise=True))
    
class BokehApp:
    
    def __init__(self):
        self.switch_key = 'ipm2'
        self.maxlen = 1000000
        
        # Initialize buffers
        self.streamHex = hv.streams.Stream.define('df', df=pd.DataFrame({'ebeam':[], 'ipm2':[]}))()
        
        # Initialize callbacks
        self.callback_id_hex = None
                
        self.ipm2_index = 0
        self.ipm3_index = 0
        self.ebeam_index = 0
        self.ipm2TS_index = 0
        self.ipm3TS_index = 0
        self.ebeamTS_index = 0
        
        self.paused_list = pd.DataFrame({'ebeam':[], 'ipm2':[], 'ipm3':[]})
        
        self.ipm2_plot = []
        self.ipm3_plot = []
        self.ebeam_plot = []
        self.ipm2TS_plot = []
        self.ipm3TS_plot = []
        self.ebeamTS_plot = []
    
    def produce_hex(self, context, doc): 
        
        # Port to connect to master
        port = 5000
        socket = context.socket(zmq.REQ)
        
        # MUST BE FROM SAME MACHINE, CHANGE IF NECESSARY!!!
        socket.connect("tcp://localhost:%d" % port)
        #socket.setsockopt(zmq.SUBSCRIBE, b"")
        

        # Generate dynamic map
        plot = hv.DynamicMap(gen_hex, streams=[self.streamHex])

        # Use bokeh to render plot
        hvplot = renderer.get_plot(plot, doc)

        def clear():
            """
            "Clear" graphs and particular lists of server instance. Save current index
            and only plot points after that index.

            """           
            self.ipm2_index = len(self.ipm2_plot)
            self.ipm3_index = len(self.ipm3_plot)
            self.ebeam_index = len(self.ebeam_plot)
            self.ipm2TS_index = len(self.ipm2TS_plot)
            self.ipm3TS_index = len(self.ipm3TS_plot)
            self.ebeamTS_index = len(self.ebeamTS_plot)

        def push_data():
            """
            Push data into stream to be ploted on hextiles plot

            """
            
            socket.send_string("Hello")
            print("Oof")

            data_dict = socket.recv_pyobj()


            peakDict = data_dict['peakDict']
            peakTSDict = data_dict['peakTSDict']

            self.ipm2_plot = list(peakDict['peak_8'])
            self.ipm3_plot = list(peakDict['peak_9'])
            self.ebeam_plot = list(peakDict['peak_10'])
            self.ipm2TS_plot = list(peakTSDict['peak_8_TS'])
            self.ipm3TS_plot = list(peakTSDict['peak_9_TS'])
            self.ebeamTS_plot = list(peakTSDict['peak_10_TS'])

            ipm2Data = pd.Series(
                self.ipm2_plot[self.ipm2_index:], 
                index=self.ipm2TS_plot[self.ipm2TS_index:])

            ipm3Data = pd.Series(
                self.ipm3_plot[self.ipm3_index:], 
                index=self.ipm3TS_plot[self.ipm3TS_index:])

            ebeamData = pd.Series(
                self.ebeam_plot[self.ebeam_index:], 
                index=self.ebeamTS_plot[self.ebeamTS_index:])

            zipped = basic_event_builder(ipm2=ipm2Data, ipm3=ipm3Data, ebeam=ebeamData)
            data = zipped[['ebeam', self.switch_key]]
            self.paused_list = zipped
            self.streamHex.event(df=data)

        
        # Because of how the ZMQ pipe works, if you pause it, then the graph is delayed by however
        # long it's paused for (so instead of updating all the missed data at once, it'll try to read
        # each pipe send)
        def play_graph():
            """
            Provide play and pause functionality to the graph

            """

            if startButton.label == '► Play':
                startButton.label = '❚❚ Pause'
                self.callback_id_hex = doc.add_periodic_callback(push_data, 1000)
            else:
                startButton.label = '► Play'
                doc.remove_periodic_callback(self.callback_id_hex)

        def saveFile():
            """
            Save current data plotted to csv file as a pandas.DataFrame

            """

            ipm2Data = pd.Series(
                self.ipm2_plot[self.ipm2_index:], 
                index=self.ipm2TS_plot[self.ipm2TS_index:])

            ipm3Data = pd.Series(
                self.ipm3_plot[self.ipm3_index:], 
                index=self.ipm3TS_plot[self.ipm3TS_index:])

            ebeamData = pd.Series(
                self.ebeam_plot[self.ebeam_index:], 
                index=self.ebeamTS_plot[self.ebeamTS_index:])
            
            zipped = basic_event_builder(ipm2=ipm2Data, ipm3=ipm3Data, ebeam=ebeamData)
            zipped.to_csv('data_class.csv')

        # Need to add function to switch while paused as well

        def switch(attr, old, new):
            """
            Switch hextiles plot when drop down menu value is updated

            """

            self.switch_key = select.value

        def switch_on_pause(attr, old, new):
            if startButton.label == '► Play':
                self.streamHex.event(df=self.paused_list[['ebeam', self.switch_key]])

        self.callback_id_hex = doc.add_periodic_callback(push_data, 1000)

        # Create widgets
        clearButton = Button(label='Clear')
        clearButton.on_click(clear)

        saveButton = Button(label='Save')
        saveButton.on_click(saveFile)

        select = Select(title="ipm value:", value="ipm2", options=["ipm2", "ipm3"])
        select.on_change('value', switch)
        select.on_change('value', switch_on_pause)

        startButton = Button(label='❚❚ Pause')
        startButton.on_click(play_graph)

        # Layout
        row_buttons = row([widgetbox([startButton, clearButton, saveButton], sizing_mode='stretch_both')])

        plot = layout([[hvplot.state], 
                       widgetbox([startButton, clearButton, saveButton], sizing_mode='stretch_both'), 
                       widgetbox([select])])


        doc.title = "Hextiles Graph"
        doc.add_root(plot)
    
    
def make_document(context, doc):
    """
    Create an instance of BokehApp() for each instance of the server
    
    """
    
    bokehApp = BokehApp()
    
    bokehApp.produce_hex(context, doc)
    
def launch_server():
   
    context = zmq.Context()

    origins = ["localhost:{}".format(5007)]
    
    apps = {'/': Application(FunctionHandler(partial(make_document, context)))}
    server = Server(apps, port=5007)
    
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
