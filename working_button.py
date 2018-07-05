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
sys.path.append('/reg/neh/home/snelson/gitMaster_smalldata_tools/smalldata_tools/smalldata_tools')
sys.path.append('/reg/neh/home/snelson/gitMaster_smalldata_tools/')

renderer = hv.renderer('bokeh').instance(mode='server')

data = tables.open_file('/reg/neh/operator/xppopr/experiments/xppx29516/xppx29516_Run140.h5').root

ebeamL3Data = data.ebeam.L3_energy.read()
ipm2Data = data.ipm2.sum.read()
ipm3Data = data.ipm3.sum.read()

actualData = pd.DataFrame({'ebeam':ebeamL3Data, 'ipm2':ipm2Data})

# Get bounds for graph
a = actualData["ipm2"].quantile(0.99)
b = actualData["ebeam"].quantile(0.99)
c = actualData["ipm2"].quantile(0.01)
d = actualData["ebeam"].quantile(0.01)


# Create the holoviews app 
def testing(run):
    return hv.HexTiles(pd.DataFrame({'ebeam':ebeamL3Data[:run],'ipm2':ipm2Data[:run]}))

counter = 0
stream = hv.streams.Stream.define('run', run=0)()
dmap = hv.DynamicMap(testing, streams=[stream]).options(cmap = "fire",
                                    bgcolor = "white", apply_ranges = True).redim.range(ebeam = (d, b),
                                    ipm2 = (c, a)).opts(norm=dict(framewise=True))

def modify_doc(doc):
    # Create HoloViews plot and attach the document
    hvplot = renderer.get_plot(dmap, doc)
    
    limit = 80000
    
    def fake_tick():
        global counter
        if counter >= limit:
            counter = 0
        else:
            counter += 100
            stream.event(run=counter)
   
    callback_id = None

    def animate():
        global callback_id
        if button.label == '► Play':
            button.label = '❚❚ Pause'
            callback_id = doc.add_periodic_callback(fake_tick, 50)
        else:
            button.label = '► Play'
            doc.remove_periodic_callback(callback_id)
            print(ebeamL3Data[counter])
            #export_png(plot, filename="plot.png")
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