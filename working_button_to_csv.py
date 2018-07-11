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
    
    if len(checkList.index) > len(df.index): 
        print("FAIL")
        
    checkList = df.copy()
    #print(df.index)
    
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

# NOTE: Change to deque
# Get data from ophyd device
data = FakeBeam()
ipm2List = []
ebeamList = []
# ipm2TimeStamp = []
# ebeamTimeStamp = []

checkList = pd.DataFrame({'ebeam':ebeamList, 'ipm2':ipm2List})

# Unsure why, but there's usually a brief flash of points at the beginning. Need to fix?

# def new_data(*args, **kwargs):
    
#     kwargs['in_value'].append(kwargs['value'])
#     kwargs['in_time'].append(kwargs['timestamp'])
    
def new_data(*args, **kwargs):
    global ipm2List, ebeamList
    ipm2 = data.fake_ipm2.get()
    ebeam = data.fake_L3.get()
    ipm2List.append(ipm2)
    ebeamList.append(ebeam)
    # print(len(ipm2List))

    
data.fake_L3.subscribe(new_data)
    
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
    def updateGraph():
        global callback_id
        if startButton.label == '► Play':
            startButton.label = '❚❚ Pause'
            callback_id = doc.add_periodic_callback(fake_tick, 1000)
        else:
            startButton.label = '► Play'
            doc.remove_periodic_callback(callback_id)
            
    def saveFile():
        # Write data to csv file
        dataFile = pd.DataFrame({'ebeam':ebeamList, 'ipm2':ipm2List})
        dataFile.to_csv('data2.csv')
        
        print(len(ebeamList))
        print("Saved!")
            
    # clear, start, save buttons        
    startButton = Button(label='► Play', width=60)
    startButton.on_click(updateGraph)
    
    saveButton = Button(label='Save', width=60)
    saveButton.on_click(saveFile)
    
    # Combine the holoviews plot and widgets in a layout
    plot = layout([
    [hvplot.state],
    widgetbox([startButton, saveButton])], sizing_mode='fixed')
    
    doc.add_root(plot)
    return doc

# To display in a script
modify_doc(curdoc()) 
