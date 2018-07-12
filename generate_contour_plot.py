import numpy as np
import holoviews as hv
import pandas as pd

import sys
from bokeh.io import show
from bokeh.layouts import layout, widgetbox
from bokeh.models import Button, Slider
from bokeh.plotting import curdoc
from bokeh.io import output_file, save, export_png
import tables
from data_getter import ipm2List, ebeamList, new_data, beam

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
                            kdims=['ebeamL3','ipm2']).options(show_legend=False).redim.range(z = (low, high))
    # If used filled=False, legend will appear, can't figure out why    
    return hv.operation.contours(img_less_bins, filled = False).options(cmap = 'fire', height = 500, width = 500)


# Make scatter plot
def gen_scatter(df):
    return hv.Scatter(df).options(size=20)

beam.fake_L3.subscribe(new_data)

dmap = hv.DynamicMap(background, streams=[stream])
dmap2 = hv.DynamicMap(gen_scatter, streams=[stream2])

combined = (dmap*dmap2).options(show_legend=False)

limit = 50

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
        global ebeamList, ipm2List, old_length, limit
        
        ebeamConverted = list(ebeamList)
        ipm2Converted = list(ipm2List)
        
        data = pd.DataFrame({
            'ebeam':ebeamConverted[-limit:],
            'ipm2':ipm2Converted[-limit:]
        })
        stream2.event(df=data)

    # Control number of dots on scatter plot
    def limit_update(attr, old, new):
        global limit
        limit = slider.value
        
    callback_id = doc.add_periodic_callback(scatter_tick, 500)

    button = Button(label='Update', width=60)
    button.on_click(click)
        
    slider = Slider(start=10, end=1000, value=50, step=1, title="Number of Events")
    slider.on_change('value', limit_update)
    
    plot = layout([
    [hvplot.state],
    widgetbox([button, slider])
    ], sizing_mode='fixed')
    
    doc.add_root(plot)
    return doc

update(curdoc())
