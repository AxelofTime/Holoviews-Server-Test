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

renderer = hv.renderer('bokeh')

data = pd.read_csv('data.csv', index_col='Unnamed: 0')

# Stream for contour plot
stream = hv.streams.Stream.define('df', df=data)()

# Stream for scatter plot
stream2 = hv.streams.Stream.define(
    'df', df=pd.DataFrame({
        'ebeam':[], 'ipm2':[]
    }))()


# Create contour plot
def background(df):
    
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

    img_less_bins = hv.Image(iSig, bounds = (ybins[0], xbins[0], ybins[-1], xbins[-1]),
                            kdims=['ebeamL3','ipm2']).redim.range(z = (low, high))
        
    return hv.operation.contours(img_less_bins, filled = True).options(cmap = 'fire', height = 500, width = 500)

# Get live data
data = FakeBeam()
ipm2List = []
ebeamList = []

def new_data(*args, **kwargs):
    global ipm2List, ebeamList
    ipm2 = data.fake_ipm2.get()
    ebeam = data.fake_L3.get()
    ipm2List.append(ipm2)
    ebeamList.append(ebeam)

# Use old_length as counter to update scatter plot
old_length = len(ipm2List)

# Make scatter plot
def gen_scatter(df):
    return hv.Scatter(df)#.opts(size_index=20)#.redim.range(ebeam=(14420, 14450), ipm2=(0, 1.3))

data.fake_L3.subscribe(new_data)

dmap = hv.DynamicMap(background, streams=[stream])
dmap2 = hv.DynamicMap(gen_scatter, streams=[stream2])

combined = dmap*dmap2

def update(doc):
    # Update graph based on new data
    
    hvplot = renderer.get_plot(combined, doc)
    
    callback_id = None
    
    # Update background if needed for new data
    def click():
        newData = pd.read_csv('data.csv', index_col='Unnamed: 0')
        stream.event(df=newData)
    
    # Update scatter_tick once new points appear
    def scatter_tick():
        global ebeamList, ipm2List, old_length
        limit = 50
        if old_length < len(ipm2List) - limit:
            old_length = len(ipm2List)
            data = pd.DataFrame({
                'ebeam':ebeamList[-limit:], 'ipm2':ipm2List[-limit:]
            })
            stream2.event(df=data)
        
    callback_id = doc.add_periodic_callback(scatter_tick, 500)

    button = Button(label='Update', width=60)
    button.on_click(click)
    
    plot = layout([
    [hvplot.state],
    [button]], sizing_mode='fixed')
    
    doc.add_root(plot)
    return doc

update(curdoc())
