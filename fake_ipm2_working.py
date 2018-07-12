# Based off example from: http://holoviews.org/user_guide/Deploying_Bokeh_Apps.html

import numpy as np
import holoviews as hv
import pandas as pd

import sys
from bokeh.io import show
from bokeh.layouts import layout, widgetbox
from bokeh.models import Button
from bokeh.plotting import curdoc
from bokeh.io import output_file, save, export_png
import tables
from fake_beam import FakeBeam
from functools import partial
from data_getter import ipm2List, ebeamList, new_data, beam

renderer = hv.renderer('bokeh').instance(mode='server')

# Create the HexTiles plot
def genHex(df):
    # Get bounds for graph
    global checkList
    colNames = list(df)
    lowX = df[colNames[0]].quantile(0.01)
    highX = df[colNames[0]].quantile(0.99)
    lowY = df[colNames[1]].quantile(0.01)
    highY = df[colNames[1]].quantile(0.99)
    
    # if len(checkList.index) > len(df.index): 
    #    print("FAIL")
        
    checkList = df.copy()
    print(df.index)
    
    return hv.HexTiles(df, group="Number of events: " + str(len(df.index))).redim.range(
        ebeam=(lowX, highX), 
        ipm2 = (lowY, highY)).opts(
        norm=dict(framewise=True))


stream = hv.streams.Stream.define(
    'df', df=pd.DataFrame({
        'ebeam':[], 'ipm2':[]
    }))()

dmap = hv.DynamicMap(
    genHex,
    streams=[stream])

# ipm2TimeStamp = []
# ebeamTimeStamp = []

checkList = pd.DataFrame({'ebeam':ebeamList, 'ipm2':ipm2List})

# Unsure why, but there's usually a brief flash of points at the beginning. Need to fix?

# def new_data(*args, **kwargs):
    
#     kwargs['in_value'].append(kwargs['value'])
#     kwargs['in_time'].append(kwargs['timestamp'])
    
beam.fake_L3.subscribe(new_data)
    
# data.fake_ipm2.subscribe(
#     partial(new_data, in_value=ipm2List, in_time=ipm2TimeStamp)
# )

# data.fake_L3.subscribe(
#     partial(new_data, in_value=ebeamList, in_time=ebeamTimeStamp)
# )

def modify_doc(doc):
    # Create HoloViews plot and attach the document
    hvplot = renderer.get_plot(dmap, doc)   
    
    # Stream data into plot
    def fake_tick():
        global ebeamList, ipm2List
        data = pd.DataFrame({
            'ebeam':ebeamList, 'ipm2':ipm2List
        })
        stream.event(df=data)
   
    callback_id = None

    # Give button functions
    
    
    # WARNING: Occasional bug with clear? Sometimes, after clear, graph turns white?
    # Note: Need to fix!
    def clear():
        # Clears data and resets graph
        global ebeamList, ipm2List
        ipm2List.clear()
        ebeamList.clear()
        print("Clear")
            
    def saveFile():
        # Write data to csv file
        dataFile = pd.DataFrame({'ebeam':ebeamList, 'ipm2':ipm2List})
        dataFile.to_csv('data2.csv')
        
        print(len(ebeamList))
        print("Saved!")
        
    def updateGraph():
        # Pause updating or not
        global callback_id
        if startButton.label == '► Play':
            startButton.label = '❚❚ Pause'
            callback_id = doc.add_periodic_callback(fake_tick, 1000)
        else:
            startButton.label = '► Play'
            doc.remove_periodic_callback(callback_id)
            
    # clear, start, save buttons 
    clearButton = Button(label='Clear', width=60)
    clearButton.on_click(clear)
    
    saveButton = Button(label='Save', width=60)
    saveButton.on_click(saveFile)
    
    startButton = Button(label='► Play', width=60)
    startButton.on_click(updateGraph)
    
    # Combine the holoviews plot and widgets in a layout
    plot = layout([
    [hvplot.state],
    widgetbox([startButton, saveButton, clearButton])], sizing_mode='fixed')
    
    doc.add_root(plot)
    return doc

# To display in a script
modify_doc(curdoc()) 
