import numpy as np
import holoviews as hv
import pandas as pd

import sys
from bokeh.io import show
from bokeh.layouts import layout, widgetbox, row
from bokeh.models import Button, Slider, Select, HoverTool
from bokeh.plotting import curdoc
from bokeh.io import output_file, save, export_png
from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
import tables
from fake_beam import FakeBeam
from functools import partial
from collections import deque
from event_builder import basic_event_builder
from threading import Lock
import logging 

renderer = hv.renderer('bokeh').instance(mode='server')

# Create contour plot
def gen_background(df):
    
    colNames = list(df)
    ebeamL3 = df[colNames[0]].astype(float)
    ipmValue = df[colNames[1]].astype(float)
   
    #Reverse xbins array to provide the correct y-axis 
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
    x = colNames[0] + " testing"
    y = colNames[1] + " testing"
    
    img_less_bins = hv.Image(
        iSig, 
        bounds=(ybins[0], xbins[0], ybins[-1], xbins[-1]), 
        kdims=[x, y]).options(
        show_legend=False).redim.range(z=(low, high))
    
    return hv.operation.contours(
        img_less_bins, 
        filled=False, group="General Contour Plot").options(
        cmap='fire').opts(
        norm=dict(framewise=True))

def gen_hex(df):
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

# Make scatter plot
def gen_scatter(df):
    return hv.Scatter(df).options(size=10, tools=['hover'], apply_ranges=False)

def produce_hex(doc, ipm2List, ipm3List, ebeamList, ipm2TS, ipm3TS, ebeamTS):    
    ipm2_plot = list(ipm2List)
    ipm3_plot = list(ipm3List)
    ebeam_plot = list(ebeamList)
    ipm2TS_plot = list(ipm2TS)
    ipm3TS_plot = list(ipm3TS)
    ebeamTS_plot = list(ebeamTS)
    
    ipm2_index, ipm3_index, ebeam_index, ipm2TS_index, ipm3TS_index, ebeamTS_index = (0, 0, 0, 0, 0, 0)
    
    # Streams
    streamHex = hv.streams.Stream.define(
        'df', df=pd.DataFrame({
            'ebeam':[], 'ipm2':[]
        }))()
    
    # Generate dynamic map
    plot = hv.DynamicMap(
        gen_hex,
        streams=[streamHex])
    
    hvplot = renderer.get_plot(plot, doc)
    
    callback_id_scatter = None
    switch_key_hex = 'ipm2'
    
    def clear():
        nonlocal ipm2_index, ipm3_index, ebeam_index, ipm2TS_index, ipm3TS_index, ebeamTS_index
        
        ipm2_index = len(ipm2List)
        ipm3_index = len(ipm3List)
        ebeam_index = len(ebeamList)
        ipm2TS_index = len(ipm2TS)
        ipm3TS_index = len(ipm3TS)
        ebeamTS_index = len(ebeamTS)
        
    def push_data():
        nonlocal ipm2_plot, ipm3_plot, ebeam_plot, ipm2TS_plot, ipm3TS_plot, ebeamTS_plot
        
        ipm2_plot = list(ipm2List)[ipm2_index:]
        ipm3_plot = list(ipm3List)[ipm3_index:]
        ebeam_plot = list(ebeamList)[ebeam_index:]
        ipm2TS_plot = list(ipm2TS)[ipm2TS_index:]
        ipm3TS_plot = list(ipm3TS)[ipm3TS_index:]
        ebeamTS_plot = list(ebeamTS)[ebeamTS_index:]
        
        ipm2Data = pd.Series(ipm2_plot, index=ipm2TS_plot)
        ipm3Data = pd.Series(ipm3_plot, index=ipm3TS_plot)
        ebeamData = pd.Series(ebeam_plot, index=ebeamTS_plot)
        zipped = basic_event_builder(ipm2=ipm2Data, ipm3=ipm3Data, ebeam=ebeamData)
        data = zipped[['ebeam', switch_key_hex]]
        streamHex.event(df=data)
    
    def play_graph():
        nonlocal callback_id_scatter
        if startButton.label == '► Play':
            startButton.label = '❚❚ Pause'
            callback_id_scatter = doc.add_periodic_callback(push_data, 1000)
        else:
            startButton.label = '► Play'
            doc.remove_periodic_callback(callback_id_scatter)
            
    # Write data to csv file
    def saveFile():
        ipm2Data = pd.Series(ipm2_plot, index=ipm2TS_plot)
        ipm3Data = pd.Series(ipm3_plot, index=ipm3TS_plot)
        ebeamData = pd.Series(ebeam_plot, index=ebeamTS_plot)
        zipped = basic_event_builder(ipm2=ipm2Data, ipm3=ipm3Data, ebeam=ebeamData)
        zipped.to_csv('data2.csv')
    
    # Add function to switch while paused as well        
    def switch(attr, old, new):
        nonlocal switch_key_hex
        switch_key_hex = select.value
    
    clearButton = Button(label='Clear')
    clearButton.on_click(clear)
    
    saveButton = Button(label='Save')
    saveButton.on_click(saveFile)
    
    select = Select(title="ipm value:", value="ipm2", options=["ipm2", "ipm3"])
    select.on_change('value', switch)
    
    startButton = Button(label='► Play')
    startButton.on_click(play_graph)
    
    row_buttons = row([widgetbox([startButton, clearButton, saveButton], sizing_mode='stretch_both')])
    
    plot = layout([[hvplot.state], 
                   widgetbox([startButton, clearButton, saveButton], sizing_mode='stretch_both'), 
                   widgetbox([select])])
                       
    #plot = layout([[hvplot.state],widgetbox([startButton, select, clearButton, saveButton])], sizing_mode='fixed')
    
    doc.add_root(plot)
    
def produce_scatter_on_background(doc, ipm2List, ipm3List, ebeamList, ipm2TS, ipm3TS, ebeamTS):
    
    # Interesting error, background doesn't seem to update after running multiple instances to the latest version and starts
    # off with the data the first instance was given. Need to figure out why!
    
    # Still has the freezing points error, though, it seems to come more frequently. This may be a bigger problem now
    curBackData = pd.read_csv('data2.csv', index_col='Unnamed: 0')
    
    # Streams
    streamContour = hv.streams.Stream.define(
        'df', df=curBackData)()

    streamScatter = hv.streams.Stream.define(
        'df', df=pd.DataFrame({
            'ebeam':[], 'ipm2':[]
        }))()
    
    # Dynamic Map
    dmapBackground = hv.DynamicMap(
        gen_background,
        streams=[streamContour])
    
    dmapScatter = hv.DynamicMap(
        gen_scatter, 
        streams=[streamScatter])
    
    overlay = (dmapBackground*dmapScatter).options(show_legend=False).opts(norm=dict(axiswise=True))
    
    hvplot = renderer.get_plot(overlay, doc)
    
    callback_id2 = None
    switch_key_scatter = 'ipm2'
    limit = 50
    
    def scatter_tick():
        
        ebeamConverted = list(ebeamList)
        ipm2Converted = list(ipm2List)
        ipm3Converted = list(ipm3List)
        ebeamTimeConverted = list(ebeamTS)
        ipm2TimeConverted = list(ipm2TS)
        ipm3TimeConverted = list(ipm3TS)

        ipm2Data = pd.Series(ipm2Converted[-limit:], index=ipm2TimeConverted[-limit:])
        ipm3Data = pd.Series(ipm3Converted[-limit:], index=ipm3TimeConverted[-limit:])
        ebeamData = pd.Series(ebeamConverted[-limit:], index=ebeamTimeConverted[-limit:])
        zipped = basic_event_builder(ipm2=ipm2Data, ipm3=ipm3Data, ebeam=ebeamData)

        scatterList = zipped[-limit:]
        
        data = scatterList[['ebeam', switch_key_scatter]]
      
        streamScatter.event(df=data)
    
    def limit_update(attr, old, new):
        nonlocal limit
        limit = limitSlider.value
    
    def switch(attr, old, new):
        nonlocal switch_key_scatter
        switch_key_scatter = select.value
    
    def switch_background(attr, old, new):
        nonlocal curBackData
        data = curBackData[['ebeam', switch_key_scatter]]
        streamContour.event(df=data)
        
    def update_background():
        nonlocal curBackData
        newData = pd.read_csv('data2.csv', index_col='Unnamed: 0')
        curBackData = newData
        data = newData[['ebeam', switch_key_scatter]]
        
        streamContour.event(df=data)
    
    callback_id2 = doc.add_periodic_callback(scatter_tick, 500)
    
    limitSlider = Slider(start=10, end=1000, value=50, step=1, title="Number of Events")
    limitSlider.on_change('value', limit_update)
    
    select = Select(title="ipm value:", value="ipm2", options=["ipm2", "ipm3"])
    select.on_change('value', switch)
    select.on_change('value', switch_background)
    
    updateButton = Button(label='Update', width=60)
    updateButton.on_click(update_background)
    
    plot = layout([[hvplot.state], 
                   widgetbox([limitSlider, select, updateButton], sizing_mode='stretch_both')])
    
    doc.add_root(plot)

def new_data(*args, **kwargs):
    
    kwargs['in_value'].append(kwargs['value'])
    kwargs['in_time'].append(kwargs['timestamp'])

def launch_server():
    
    # Get data
    beam = FakeBeam()
    ipm2List = deque(maxlen=100000)
    ipm3List = deque(maxlen=100000)
    ebeamList = deque(maxlen=100000)
    ipm2TimeStamp = deque(maxlen=100000)
    ipm3TimeStamp = deque(maxlen=100000)
    ebeamTimeStamp = deque(maxlen=100000)
    
    beam.fake_ipm2.subscribe(
        partial(new_data, in_value=ipm2List, in_time=ipm2TimeStamp)
    )

    beam.fake_ipm3.subscribe(
        partial(new_data, in_value=ipm3List, in_time=ipm3TimeStamp)
    )

    beam.fake_L3.subscribe(
        partial(new_data, in_value=ebeamList, in_time=ebeamTimeStamp)
    )
    
    origins = ["localhost:{}".format(5006)]
    
    server = Server(
        {
            '/Hextiles': partial(
                produce_hex,
                ipm2List=ipm2List,
                ipm3List=ipm3List,
                ebeamList=ebeamList,
                ipm2TS=ipm2TimeStamp,
                ipm3TS=ipm3TimeStamp,
                ebeamTS=ebeamTimeStamp#,
                #streamHex=streamHex
            ),
            '/Contour': partial(
                produce_scatter_on_background,
                ipm2List=ipm2List,
                ipm3List=ipm3List,
                ebeamList=ebeamList,
                ipm2TS=ipm2TimeStamp,
                ipm3TS=ipm3TimeStamp,
                ebeamTS=ebeamTimeStamp#,
                #streamHex=streamHex
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