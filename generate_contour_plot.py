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

renderer = hv.renderer('bokeh')

data = pd.read_csv('data.csv', index_col='Unnamed: 0')

stream = hv.streams.Stream.define('df', df=data)()

def make_plot(df):
    
    # Create contour plot

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

dmap = hv.DynamicMap(make_plot, streams=[stream])

def update(doc):
    # Update graph based on new data
    
    hvplot = renderer.get_plot(dmap, doc)
    
    def click():
        newData = pd.read_csv('data.csv', index_col='Unnamed: 0')
        stream.event(df=newData)

    button = Button(label='Update', width=60)
    button.on_click(click)
    
    plot = layout([
    [hvplot.state],
    [button]], sizing_mode='fixed')
    
    doc.add_root(plot)
    return doc

update(curdoc())