# Based off example from: http://holoviews.org/user_guide/Deploying_Bokeh_Apps.html

import numpy as np
import holoviews as hv
import pandas as pd

import sys
from bokeh.io import show
from bokeh.layouts import layout, widgetbox
from bokeh.models import Button, Slider, Select
from bokeh.plotting import curdoc
from bokeh.io import output_file, save, export_png
import tables
from fake_beam import FakeBeam
from functools import partial
from data_getter import ipm2List, ipm3List, ebeamList, new_data, beam

renderer = hv.renderer('bokeh').instance(mode='server')

dataContour = pd.read_csv('data.csv', index_col='Unnamed: 0')

dataDict = {'ipm2':ipm2List, 'ipm3':ipm3List, 'ebeam':ebeamList}


# NEED TO RESPONSIVE TO THE CHANGE IN THE DROPDOWN MENU!!!
# Create contour plot
def background(df):
    
    # Maybe use colNames instead of 'ebeam'?
    ebeamL3 = df['ebeam'].astype(float)
    ipm2 = df['ipm2'].astype(float)
    #Reverse xbins array to provide the correct y-axis 
    xbinsReversed = np.linspace(np.percentile(ipm2, 1), np.percentile(ipm2, 99),30)
    xbins = xbinsReversed[::-1]
    ybins = np.linspace(np.percentile(ebeamL3, 1), np.percentile(ebeamL3, 99), 30)
    ind0 = np.digitize(ipm2, xbins)
    ind1 = np.digitize(ebeamL3, ybins)
    ind2d = np.ravel_multi_index((ind0,ind1), (ybins.shape[0]+1, xbins.shape[0]+1))
    iSig = np.bincount(ind2d, minlength=(xbins.shape[0]+1)*(ybins.shape[0]+1)).reshape(xbins.shape[0]+1, ybins.shape[0]+1)
    low = np.percentile(iSig, 1)
    high = np.percentile(iSig, 99)
    
    img_less_bins = hv.Image(
        iSig, 
        bounds=(ybins[0], xbins[0], ybins[-1], xbins[-1]), 
        kdims=['ebeamL3','ipm2Stuff']).options(
        show_legend=False).redim.range(z=(low, high))
    
    return hv.operation.contours(
        img_less_bins, 
        filled=False, group="General Contour Plot").options(
        cmap='fire')

# Create the HexTiles plot
def genHex(df):
    # Get bounds for graph
    global checkList
    colNames = list(df)
    lowX = df[colNames[0]].quantile(0.01)
    highX = df[colNames[0]].quantile(0.99)
    lowY = df[colNames[1]].quantile(0.01)
    highY = df[colNames[1]].quantile(0.99)
    
    checkList = df.copy()
    #print(df.index)
    
    return hv.HexTiles(df, group="Number of events: " + str(len(df.index))).redim.range(
        ebeam=(lowX, highX), 
        ipm2 = (lowY, highY)).opts(
        norm=dict(framewise=True))

# Make scatter plot
def gen_scatter(df):
    return hv.Scatter(df).options(size=20)

# Streams
streamHex = hv.streams.Stream.define(
    'df', df=pd.DataFrame({
        'ebeam':[], 'ipm2':[]
    }))()

streamContour = hv.streams.Stream.define(
    'df', df=dataContour)()

streamScatter = hv.streams.Stream.define(
    'df', df=pd.DataFrame({
        'ebeam':[], 'ipm2':[]
    }))()

# Generate dynamic map
dmapHex = hv.DynamicMap(
    genHex,
    streams=[streamHex])
dmapBackground = hv.DynamicMap(
    background,
    streams=[streamContour])
dmapScatter = hv.DynamicMap(
    gen_scatter, 
    streams=[streamScatter])
overlay = (dmapBackground*dmapScatter).options(show_legend=False).opts(norm=dict(axiswise=True))
combined = dmapHex + overlay

# Start pushing data into deque
beam.fake_L3.subscribe(new_data)

limit = 50
key1 = 'ebeam'
key2 = 'ipm2'

def modify_doc(doc):
    # Create HoloViews plot and attach the document
    hvplot = renderer.get_plot(combined, doc)   
    
    # Stream data into plot
    def fake_tick():
        global key1, key2
        dataDict = pd.DataFrame({'ipm2':ipm2List, 'ipm3':ipm3List, 'ebeam':ebeamList})
        data = dataDict[['ebeam', key2]]
#         global ebeamList, ipm2List
#         data = pd.DataFrame({
#             'ebeam':ebeamList, 'ipm2':ipm2List
#         })
        streamHex.event(df=data)
    
    def test_run(attr, old, new):
        global key2
        key2 = select.value
    
    # Update scatter_tick once new points appear
    def scatter_tick():
        global ebeamList, ipm2List, limit
        
        ebeamConverted = list(ebeamList)
        ipm2Converted = list(ipm2List)
        
        data = pd.DataFrame({
            'ebeam':ebeamConverted[-limit:],
            'ipm2':ipm2Converted[-limit:]
        })
        streamScatter.event(df=data)
   
    callback_id = None
    callback_id2 = None
    
    
    select = Select(title="ipm value:", value="ipm2", options=["ipm2", "ipm3"])
    select.on_change('value', test_run)

    # Give button functions
    # WARNING: Occasional bug with clear? Sometimes, after clear, graph turns white?
    # Note: Need to fix!
    # Clears data and resets graph
    def clear():
        global ebeamList, ipm2List
        ipm2List.clear()
        ipm3List.clear()
        ebeamList.clear()
        print("Clear")
     
    # Write data to csv file
    def saveFile():
        dataFile = pd.DataFrame({'ebeam':ebeamList, 'ipm2':ipm2List})
        dataFile.to_csv('data2.csv')
        
        print(len(ebeamList))
        print("Saved!")
        
    # Update background if needed for new data
    
    # Note: Maybe modify the pandas dataframe from the csv before passing it to the background to make it easier on myself???
    def updateBackground():
        newData = pd.read_csv('data.csv', index_col='Unnamed: 0')
        streamContour.event(df=newData)
    
    # Updates HexTiles plot
    def updateGraph():
        global callback_id
        if startButton.label == '► Play':
            startButton.label = '❚❚ Pause'
            callback_id = doc.add_periodic_callback(fake_tick, 1000)
        else:
            startButton.label = '► Play'
            doc.remove_periodic_callback(callback_id)
    
    # Control number of dots on scatter plot
    def limit_update(attr, old, new):
        global limit
        limit = limitSlider.value
        
    callback_id2 = doc.add_periodic_callback(scatter_tick, 500)
            
    # Bokeh widgets 
    clearButton = Button(label='Clear', width=60)
    clearButton.on_click(clear)
    
    saveButton = Button(label='Save', width=60)
    saveButton.on_click(saveFile)
    
    startButton = Button(label='► Play', width=60)
    startButton.on_click(updateGraph)
    
    updateButton = Button(label='Update', width=60)
    updateButton.on_click(updateBackground)
        
    limitSlider = Slider(start=10, end=1000, value=50, step=1, title="Number of Events")
    limitSlider.on_change('value', limit_update)
    
    # Combine the holoviews plot and widgets in a layout
    plot = layout([
    [hvplot.state],
    widgetbox([startButton, 
               saveButton, 
               clearButton, 
               updateButton, 
               limitSlider, 
               select])
    ], sizing_mode='fixed')
    
    doc.add_root(plot)
    return doc

# To display in a script
modify_doc(curdoc()) 
