import holoviews as hv
import tables
import pandas as pd
import numpy as np
from holoviews.streams import Buffer, Pipe
from bokeh.plotting import curdoc
from bokeh.server.server import Server
from tornado.ioloop import PeriodicCallback, IOLoop
from tornado import gen

renderer = hv.renderer('bokeh')
options = hv.Store.options(backend='bokeh')

# Get data
data = tables.open_file('/reg/neh/operator/xppopr/experiments/xppx29516/xppx29516_Run140.h5').root
ebeamL3 = data.ebeam.L3_energy.read()
ipm2 = data.ipm2.sum.read()

actualData = pd.DataFrame({'ebeam':ebeamL3, 'ipm2':ipm2})

# NOTE: Figured out way to redim the graph without having to filter, will update in future
# Filtering the actual data, need to find way to simply redim graph without having to filter dataset
a = actualData["ipm2"].quantile(0.99)
actualData = actualData[actualData["ipm2"] < a]
b = actualData["ebeam"].quantile(0.99)
actualData = actualData[actualData["ebeam"] < b]
c = actualData["ipm2"].quantile(0.01)
actualData = actualData[actualData["ipm2"] > c]
d = actualData["ebeam"].quantile(0.01)
actualData = actualData[actualData["ebeam"] > d]

# Get filtered data from filtered data set
ebeamStuff = actualData['ebeam'].astype(float)
ipm2Stuff = actualData['ipm2'].astype(float)

@gen.coroutine
def f():
    global index
    if index < len(actualData.index) + 100:
        dfstream.send(pd.DataFrame({'ebeam':ebeamStuff[index:index+100], 
                                    'ipm2':ipm2Stuff[index:index+100]}))
        index += 100
    else: 
        #cb.stop()
        # Needs to stop loop

# Starting data set
testData = pd.DataFrame({'ebeam':ebeamL3[:100],'ipm2':ipm2[:100]})

# Filtering starting data set
testData = testData[testData["ipm2"] < a]
testData = testData[testData["ebeam"] < b]
testData = testData[testData["ipm2"] > c]
testData = testData[testData["ebeam"] > d]

dfstream = Buffer(testData, length=100000, index=False) # Length is long to keep previous points plotted
index = 100

PeriodicCallback(f, 1).start()
doc = renderer.server_doc(hv.DynamicMap(hv.Points, streams=[dfstream]))

doc.title = 'HoloViews App'
