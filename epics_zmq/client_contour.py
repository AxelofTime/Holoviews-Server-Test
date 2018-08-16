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

def gen_background(df):
    """
    Return holoviews contour plot based on image generated from data
    
    Parameters
    ----------
    
    df: pandas.DataFrame
        DataFrame containing data to be ploted on contour plot
        
    """
    
    colNames = list(df)
    ebeamL3 = df[colNames[0]].astype(float)
    ipmValue = df[colNames[1]].astype(float)
   
    #Reverse xbins array to provide the correct y-axis (otherwise it's flipped)
    xbinsReversed = np.linspace(np.percentile(ipmValue, 1), np.percentile(ipmValue, 99),30)
    xbins = xbinsReversed[::-1]
    ybins = np.linspace(np.percentile(ebeamL3, 1), np.percentile(ebeamL3, 99), 30)
    ind0 = np.digitize(ipmValue, xbins)
    ind1 = np.digitize(ebeamL3, ybins)
    ind2d = np.ravel_multi_index((ind0,ind1), (ybins.shape[0]+1, xbins.shape[0]+1))
    iSig = np.bincount(ind2d, minlength=(xbins.shape[0]+1)*(ybins.shape[0]+1)).reshape(xbins.shape[0]+1, ybins.shape[0]+1)
    low = np.percentile(iSig, 1)
    high = np.percentile(iSig, 99)
    
    # Changing axis names so they don't match HexTiles names
    x = colNames[0] + " Contour"
    y = colNames[1] + " Contour"
    
    img_less_bins = hv.Image(
        iSig, bounds=(ybins[0], xbins[0], ybins[-1], xbins[-1]), kdims=[x, y]).options(
        show_legend=False).redim.range(
        z=(low, high))
    
    return hv.operation.contours(
        img_less_bins, filled=False, group="General Contour Plot").options(
        cmap='fire').opts(
        norm=dict(framewise=True))
    
def gen_scatter(df):
    """
    Return holoviews scatter plot
    
    Parameters
    ----------
    
    df: pandas.DataFrame
        DataFrame containing data to be ploted on scatter plot
    
    """
    print(df.head())
    return hv.Scatter(df).options(size=10, tools=['hover'], apply_ranges=False)
    
class BokehApp:
    
    def __init__(self):
        self.switch_key = 'ipm2'
        self.maxlen = 1000000
        
        self.curBackData = pd.read_csv('data_class.csv', index_col='Unnamed: 0')
        
        # Initialize buffers
        self.streamContour = hv.streams.Stream.define('df', df=self.curBackData)()
        self.streamScatter = hv.streams.Stream.define('df', df=pd.DataFrame({'ebeam':[], 'ipm2':[]}))()
        
        # Initialize callbacks
        self.callback_id_scatter = None
                
        self.ipm2_index = 0
        self.ipm3_index = 0
        self.ebeam_index = 0
        self.ipm2TS_index = 0
        self.ipm3TS_index = 0
        self.ebeamTS_index = 0
        
        self.limit = 50
        
        self.paused_list = pd.DataFrame({'ebeam':[], 'ipm2':[], 'ipm3':[]})
        
        self.ipm2_plot = []
        self.ipm3_plot = []
        self.ebeam_plot = []
        self.ipm2TS_plot = []
        self.ipm3TS_plot = []
        self.ebeamTS_plot = []
        
    def produce_scatter_on_background(self, context, doc):

        # Interesting error, background doesn't seem to update after running multiple instances 
        # to the latest version and starts off with the data the first instance was given. 
        # Need to figure out why!

        # Port to connect to master
        port = 5000
        socket = context.socket(zmq.SUB)
        
        # MUST BE FROM SAME MACHINE, CHANGE IF NECESSARY!!!
        socket.connect("tcp://localhost:%d" % port)
        socket.setsockopt(zmq.SUBSCRIBE, b"")        

        # Dynamic Map
        dmapBackground = hv.DynamicMap(gen_background, streams=[self.streamContour])

        dmapScatter = hv.DynamicMap(gen_scatter, streams=[self.streamScatter])

        overlay = (dmapBackground*dmapScatter).options(show_legend=False).opts(norm=dict(axiswise=True))

        # Render plot with bokeh
        hvplot = renderer.get_plot(overlay, doc)    

        def scatter_tick():
            """
            Push new scatter points into stream to plot.

            """
            # Still has the freezing points error, though, it seems to come more frequently. 
            # This may be a bigger problem now
            
            if socket.poll(timeout=0):
                
                data_dict = socket.recv_pyobj()
                peakDict = data_dict['peakDict']
                peakTSDict = data_dict['peakTSDict']
                
                self.ipm2_plot = list(peakDict['peak_8'])
                self.ipm3_plot = list(peakDict['peak_9'])
                self.ebeam_plot = list(peakDict['peak_10'])
                self.ipm2TS_plot = list(peakTSDict['peak_8_TS'])
                self.ipm3TS_plot = list(peakTSDict['peak_9_TS'])
                self.ebeamTS_plot = list(peakTSDict['peak_10_TS'])

                ipm2Data = pd.Series(self.ipm2_plot[-self.limit:], index=self.ipm2TS_plot[-self.limit:])
                ipm3Data = pd.Series(self.ipm3_plot[-self.limit:], index=self.ipm3TS_plot[-self.limit:])
                ebeamData = pd.Series(self.ebeam_plot[-self.limit:], index=self.ebeamTS_plot[-self.limit:])
    
                zipped = basic_event_builder(ipm2=ipm2Data, ipm3=ipm3Data, ebeam=ebeamData)

                scatterList = zipped

                data = scatterList[['ebeam', self.switch_key]]
                self.paused_list = scatterList

                self.streamScatter.event(df=data)

        def limit_update(attr, old, new):
            """
            Update limit slider value

            """
            self.limit = limitSlider.value

        def switch(attr, old, new):
            """
            Update drop down menu value

            """

            self.switch_key = select.value

        def switch_background(attr, old, new):
            """
            Switch background when drop down menu value is updated

            """

            data = self.curBackData[['ebeam', self.switch_key]]
            self.streamContour.event(df=data)

       
        def switch_on_pause(attr, old, new):
            if startButton.label == '► Play':

                self.streamScatter.event(df=self.paused_list[['ebeam', self.switch_key]])

        # Scatter plot may freeze when update background occurs?
        def update_background():
            """
            Update background with most updated data when update button is pressed

            """

            newData = pd.read_csv('data_class.csv', index_col='Unnamed: 0')
            self.curBackData = newData
            data = newData[['ebeam', self.switch_key]]

            self.streamContour.event(df=data)

        def play_graph():
            """
            Provide play and pause functionality to the graph

            """

            if startButton.label == '► Play':
                startButton.label = '❚❚ Pause'
                self.callback_id_scatter = doc.add_periodic_callback(scatter_tick, 1000)
            else:
                startButton.label = '► Play'
                doc.remove_periodic_callback(self.callback_id_scatter)

        # Continuously update scatter plot
        self.callback_id_scatter = doc.add_periodic_callback(scatter_tick, 1000)

        # Create widgets
        limitSlider = Slider(start=10, end=1000, value=50, step=1, title="Number of Events")
        limitSlider.on_change('value', limit_update)

        startButton = Button(label='❚❚ Pause')
        startButton.on_click(play_graph)

        select = Select(title="ipm value:", value="ipm2", options=["ipm2", "ipm3"])
        select.on_change('value', switch)
        select.on_change('value', switch_background)
        select.on_change('value', switch_on_pause)

        updateButton = Button(label='Update', width=60)
        updateButton.on_click(update_background)

        plot = layout([[hvplot.state], 
                       widgetbox([limitSlider, select, updateButton, startButton], sizing_mode='stretch_both')])

        doc.title = "Reference Graph"
        doc.add_root(plot)
     
    
def make_document(context, doc):
    """
    Create an instance of BokehApp() for each instance of the server
    
    """
    
    bokehApp = BokehApp()
    
    bokehApp.produce_scatter_on_background(context, doc)
    
def launch_server():
   
    context = zmq.Context()

    origins = ["localhost:{}".format(5008)]
    
    apps = {'/': Application(FunctionHandler(partial(make_document, context)))}
    server = Server(apps, port=5008)
    
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
