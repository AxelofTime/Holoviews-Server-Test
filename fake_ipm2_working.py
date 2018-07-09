# Based off example from: http://holoviews.org/user_guide/Deploying_Bokeh_Apps.html

import numpy as np
import holoviews as hv
import pandas as pd

import sys
from bokeh.io import show
from bokeh.layouts import layout
from bokeh.models import Button
from bokeh.plotting import curdoc
from bokeh.io import output_file, save, export_png
import tables
from fake_beam import FakeBeam

renderer = hv.renderer('bokeh').instance(mode='server')

# Create the HexTiles plot
def genHex(df):
    return hv.HexTiles(pd.DataFrame(df))

stream = hv.streams.Stream.define('df', df=pd.DataFrame({'ebeam':[], 'ipm2':[]}))()
dmap = hv.DynamicMap(
    genHex,
    streams=[stream]).options(
    cmap = "fire",
    bgcolor = "white").redim.range(
    ebeam = (14420., 14450.),
    ipm2 = (0, 1.1)).opts(
    norm=dict(framewise=True))

# Get data from ophyd device
data = FakeBeam()
ipm2List = []
ebeamList = []

# Unsure why, but there's usually a brief flash of points at the beginning. Need to fix?
def new_data(*args, **kwargs):
    global ipm2List, ebeamList
    ipm2 = data.fake_ipm2.get()
    ebeam = data.fake_L3.get()
    ipm2List.append(ipm2)
    ebeamList.append(ebeam)
    # print(len(ipm2List))
    
data.fake_ipm2.subscribe(new_data)

def modify_doc(doc):
    # Create HoloViews plot and attach the document
    hvplot = renderer.get_plot(dmap, doc)   
    
    # Stream data into plot
    def fake_tick():
        global ebeamList, ipm2List
        print(ebeamList)
        data = pd.DataFrame({'ebeam':ebeamList, 'ipm2':ipm2List})
        stream.event(df=data)
   
    callback_id = None

    # Give button functions
    def animate():
        global callback_id
        if button.label == '► Play':
            button.label = '❚❚ Pause'
            callback_id = doc.add_periodic_callback(fake_tick, 50)
        else:
            button.label = '► Play'
            doc.remove_periodic_callback(callback_id)
            
            # Write data to csv file
            # data = pd.DataFrame({'ebeam':ebeamL3Data[:counter+100], 'ipm2':ipm2Data[:counter+100]})
            # data.to_csv('data.csv')
            # stream2.event(df=data)
            
            
    button = Button(label='► Play', width=60)
    button.on_click(animate)
    
    # Combine the holoviews plot and widgets in a layout
    plot = layout([
    [hvplot.state],
    [button]], sizing_mode='fixed')
    
    doc.add_root(plot)
    return doc

# To display in a script
modify_doc(curdoc()) 

