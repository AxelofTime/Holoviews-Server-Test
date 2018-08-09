import numpy as np
import holoviews as hv
import pandas as pd

import sys
from bokeh.io import show
from bokeh.layouts import layout, widgetbox, row
from bokeh.models import Button, Slider, Select, HoverTool, DatetimeTickFormatter
from bokeh.plotting import curdoc
from bokeh.io import output_file, save
from bokeh.server.server import Server
from bokeh.application import Application
import tables
from fake_beam import FakeBeam
from functools import partial
from collections import deque
from event_builder import basic_event_builder
from holoviews.streams import Buffer
import time

renderer = hv.renderer('bokeh').instance(mode='server')

def apply_formatter(plot, element):
    """
    Datetime formatting for x-axis ticks 
    
    """
    
    plot.handles['xaxis'].formatter = DatetimeTickFormatter(
        microseconds=['%D %H:%M:%S'], 
        milliseconds=['%D %H:%M:%S'], 
        seconds=["%D %H:%M:%S"],
        minsec=["%D %H:%M:%S"],
        minutes=['%D %H:%M:%S'], 
        hourmin=["%D %H:%M:%S"],
        hours=['%D %H:%M:%S'],
        days=['%D %H:%M:%S'], 
        months=['%D %H:%M:%S'], 
        years=['%D %H:%M:%S'])

def gen_background(df):
    """
    Return holoviews contour plot based on image generated from data
    
    Parameters
    ----------
    
    df: pandas.DataFrame
        DataFrame containing data to be ploted on contour plot
        
    """
    
    colNames = list(df)
    ebeamL3 = df[colNames[0]].astype(float)
    ipmValue = df[colNames[1]].astype(float)
   
    #Reverse xbins array to provide the correct y-axis (otherwise it's flipped)
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
    x = colNames[0] + " Contour"
    y = colNames[1] + " Contour"
    
    img_less_bins = hv.Image(
        iSig, bounds=(ybins[0], xbins[0], ybins[-1], xbins[-1]), kdims=[x, y]).options(
        show_legend=False).redim.range(
        z=(low, high))
    
    return hv.operation.contours(
        img_less_bins, filled=False, group="General Contour Plot").options(
        cmap='fire').opts(
        norm=dict(framewise=True))

def gen_hex(df):
    """
    Return holoviews HexTiles plot
    
    Parameters
    ----------
    
    df: pandas.DataFrame
        DataFrame containing data to be ploted on hextiles plot
    
    """
    
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

def gen_scatter(df):
    """
    Return holoviews scatter plot
    
    Parameters
    ----------
    
    df: pandas.DataFrame
        DataFrame containing data to be ploted on scatter plot
    
    """
    return hv.Scatter(df).options(size=10, tools=['hover'], apply_ranges=False)

def gen_timehistory(df):
    
    return hv.Curve(df).opts(norm=dict(framewise=True)) 
    
def produce_timehistory(doc, ipm2List, ipm3List, ebeamList, ipm2TS, ipm3TS, ebeamTS):
    # Streams
    
    # See if you can limit the buffer
    b_th_ipm2 = Buffer(pd.DataFrame({'ipm':[]}), length=1200)
    b_th_ipm3 = Buffer(pd.DataFrame({'ipm':[]}), length=1200)
    
    streamTH2 = hv.streams.Stream.define(
        'df', df=pd.DataFrame({
            'timestamp':[], 'ipm':[]
        }))()
    
    streamTH3 = hv.streams.Stream.define(
        'df', df=pd.DataFrame({
            'timestamp':[], 'ipm':[]
        }))()
    
    # Generate dynamic map
    
    # bottom plot
    # blue data
    plot_ipm2_b = hv.DynamicMap(
        hv.Scatter,
        streams=[b_th_ipm2]).options(width=1001, finalize_hooks=[apply_formatter])
    # red data
    plot_ipm3_b = hv.DynamicMap(
        hv.Scatter,
        streams=[b_th_ipm3]).options(color='red', finalize_hooks=[apply_formatter])

    # top plot
    # blue plot
#     plot_ipm2 = hv.DynamicMap(
#         gen_timehistory,
#         streams=[streamTH2]).options(
#         width=1000, finalize_hooks=[apply_formatter]).redim.label(
#         index='test')
#     # red plot
#     plot_ipm3 = hv.DynamicMap(
#         gen_timehistory,
#         streams=[streamTH3]).options(
#         color='red', finalize_hooks=[apply_formatter]).redim.label(
#         index='test')
    
    #plot = (plot_ipm2*plot_ipm3)# + plot_ipm2_b*plot_ipm3_b).cols(1)
    plot = plot_ipm2_b*plot_ipm3_b
    
    # Use bokeh to render plot
    hvplot = renderer.get_plot(plot, doc)
    
    callback_id_th2 = None
    callback_id_th3 = None
    
    def push_data(ipm, timestamp, stream):
        """
        Push data into stream to be ploted on hextiles plot
        
        """
                
        ipm_plot = list(ipm)
        timestamp_plot = list(timestamp)
        
        times = [1000*time for time in timestamp_plot]
        ipmData = pd.Series(ipm_plot, index=times)
        
        zipped = basic_event_builder(ipm=ipmData)
        median = zipped.rolling(120, min_periods=1).median()
        
        if type(stream) == hv.streams.Buffer:
            if len(median) > 1000:
                counter = 0
                pos = 0
                send = pd.DataFrame({'ipm':[]})
                
                while counter < 1000:
                    
                    divide = len(median)/1000. 
                    test = int(pos)
                    send = send.append(median.iloc[[test]])
                    #print(send)
                    #print(type(median.iloc[[test]]))
                    pos += divide
                    counter += 1
                    
                #print(len(send))
                #print(len(stream.data))
                stream.send(send)
                #print(stream.data[-10:])
                print("Done")
                
            else:
                stream.send(median)
            #stream.send(median)
        elif len(median) > 100:
            stream.event(df=median)
            #print(len(stream.data))
        
        #stream.send(median)
        #stream.event(df=median)
        #print(type(stream))
        #print(len(median))
        
#         ipmData = pd.DataFrame({'timestamp': times, 'ipm': ipm_plot})        
        
#         stream.event(df=ipmData)
        
        
#     callback_id_th2 = doc.add_periodic_callback(
#         partial(push_data, ipm=ipm2List, timestamp=ipm2TS, stream=streamTH2), 
#         1000)
    
#     callback_id_th3 = doc.add_periodic_callback(
#         partial(push_data, ipm=ipm3List, timestamp=ipm3TS, stream=streamTH3), 
#         1000)
    
    callback_id_th2_b = doc.add_periodic_callback(
        partial(push_data, ipm=ipm2List, timestamp=ipm2TS, stream=b_th_ipm2), 
        1000)
    
    callback_id_th3_b = doc.add_periodic_callback(
        partial(push_data, ipm=ipm3List, timestamp=ipm3TS, stream=b_th_ipm3), 
        1000)
    
    plot = hvplot.state
                           
    doc.title = "Time History Graphs"
    doc.add_root(plot)
    
def produce_hex(doc, ipm2List, ipm3List, ebeamList, ipm2TS, ipm3TS, ebeamTS): 
    """
    Produce updating hextiles plot and push them onto the web page document.
    User may save current data, clear existing data, or pause the graph. User
    can also switch between ipm2 and ipm3 over ebeam graphs.
    
    Parameters
    ----------
    
    doc: bokeh.document (I think)
        Bokeh document to be displayed on webpage
    
    ipm2List: deque
        Deque containing updating ipm2 values
        
    ipm3List: deque
        Deque containing updating ipm3 values
    
    ebeamList: deque
        Deque containing updating ebeam values
    
    ipm2TS: deque
        Deque containing updating ipm2 timestamps
    
    ipm3TS: deque
        Deque containing updating ipm3 timestamps
    
    ebeamTS: deque
        Deque containing updating ebeam timestamps
    
    """
    
    # Create copy of deques for each instance of server
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
    
    # Use bokeh to render plot
    hvplot = renderer.get_plot(plot, doc)
    
    # Initialize callback id for hextiles plot
    callback_id_hex = None
    
    # Initialize values that can be updated by widgets
    switch_key_hex = 'ipm2'
    
    def clear():
        """
        "Clear" graphs and particular lists of server instance. Save current index
        and only plot points after that index.
        
        """
        
        nonlocal ipm2_index, ipm3_index, ebeam_index, ipm2TS_index, ipm3TS_index, ebeamTS_index
        
        ipm2_index = len(ipm2List)
        ipm3_index = len(ipm3List)
        ebeam_index = len(ebeamList)
        ipm2TS_index = len(ipm2TS)
        ipm3TS_index = len(ipm3TS)
        ebeamTS_index = len(ebeamTS)
        
    def push_data():
        """
        Push data into stream to be ploted on hextiles plot
        
        """
        
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
        #print(zipped)
        streamHex.event(df=data)
    
    def play_graph():
        """
        Provide play and pause functionality to the graph

        """
        
        nonlocal callback_id_hex
        if startButton.label == '► Play':
            startButton.label = '❚❚ Pause'
            callback_id_hex = doc.add_periodic_callback(push_data, 1000)
        else:
            startButton.label = '► Play'
            doc.remove_periodic_callback(callback_id_hex)
            
    def saveFile():
        """
        Save current data plotted to csv file as a pandas.DataFrame
        
        """
        
        ipm2Data = pd.Series(ipm2_plot, index=ipm2TS_plot)
        ipm3Data = pd.Series(ipm3_plot, index=ipm3TS_plot)
        ebeamData = pd.Series(ebeam_plot, index=ebeamTS_plot)
        zipped = basic_event_builder(ipm2=ipm2Data, ipm3=ipm3Data, ebeam=ebeamData)
        zipped.to_csv('data2.csv')
    
    # Need to add function to switch while paused as well
    
    def switch(attr, old, new):
        """
        Switch hextiles plot when drop down menu value is updated
        
        """
        
        nonlocal switch_key_hex
        switch_key_hex = select.value
    
    # Create widgets
    clearButton = Button(label='Clear')
    clearButton.on_click(clear)
    
    saveButton = Button(label='Save')
    saveButton.on_click(saveFile)
    
    select = Select(title="ipm value:", value="ipm2", options=["ipm2", "ipm3"])
    select.on_change('value', switch)
    
    startButton = Button(label='► Play')
    startButton.on_click(play_graph)
    
    # Layout
    row_buttons = row([widgetbox([startButton, clearButton, saveButton], sizing_mode='stretch_both')])
    
    plot = layout([[hvplot.state], 
                   widgetbox([startButton, clearButton, saveButton], sizing_mode='stretch_both'), 
                   widgetbox([select])])
                       
    #plot = layout([[hvplot.state],widgetbox([startButton, select, clearButton, saveButton])], sizing_mode='fixed')
    
    doc.title = "Hextiles Graph"
    doc.add_root(plot)
    
def produce_scatter_on_background(doc, ipm2List, ipm3List, ebeamList, ipm2TS, ipm3TS, ebeamTS):
    """
    Produce background plot with updating scatter plot on top of it 
    and push them onto the web page document. User can control how many
    points of the scatter plot appears and update the contour plot. User
    may also switch between ipm2 and ipm3 over ebeam graphs.
    
    Parameters
    ----------
    
    doc: bokeh.document (I think)
        Bokeh document to be displayed on webpage
    
    ipm2List: deque
        Deque containing updating ipm2 values
        
    ipm3List: deque
        Deque containing updating ipm3 values
    
    ebeamList: deque
        Deque containing updating ebeam values
    
    ipm2TS: deque
        Deque containing updating ipm2 timestamps
    
    ipm3TS: deque
        Deque containing updating ipm3 timestamps
    
    ebeamTS: deque
        Deque containing updating ebeam timestamps
    
    """
    
    # Interesting error, background doesn't seem to update after running multiple instances 
    # to the latest version and starts off with the data the first instance was given. 
    # Need to figure out why!
    
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
    
    # Render plot with bokeh
    hvplot = renderer.get_plot(overlay, doc)
    
    # Initialize callback for scatterplot
    callback_id_scatter = None
    
    # Initialize variables than can be updated by widgets
    switch_key_scatter = 'ipm2'
    limit = 50
    
    def scatter_tick():
        """
        Push new scatter points into stream to plot.
        
        """
        
        # Still has the freezing points error, though, it seems to come more frequently. 
        # This may be a bigger problem now
        
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
        """
        Update limit slider value
        
        """
        nonlocal limit
        limit = limitSlider.value
    
    def switch(attr, old, new):
        """
        Update drop down menu value
        
        """
        
        nonlocal switch_key_scatter
        switch_key_scatter = select.value
    
    def switch_background(attr, old, new):
        """
        Switch background when drop down menu value is updated
        
        """
        
        nonlocal curBackData
        data = curBackData[['ebeam', switch_key_scatter]]
        streamContour.event(df=data)
        
    def update_background():
        """
        Update background with most updated data when update button is pressed
        
        """
        
        nonlocal curBackData
        newData = pd.read_csv('data2.csv', index_col='Unnamed: 0')
        curBackData = newData
        data = newData[['ebeam', switch_key_scatter]]
        
        streamContour.event(df=data)
        
    def play_graph():
        """
        Provide play and pause functionality to the graph

        """
        
        nonlocal callback_id_scatter
        if startButton.label == '► Play':
            startButton.label = '❚❚ Pause'
            callback_id_scatter = doc.add_periodic_callback(scatter_tick, 1000)
        else:
            startButton.label = '► Play'
            doc.remove_periodic_callback(callback_id_scatter)
    
    # Continuously update scatter plot
    #callback_id_scatter = doc.add_periodic_callback(scatter_tick, 500)
    
    # Create widgets
    limitSlider = Slider(start=10, end=1000, value=50, step=1, title="Number of Events")
    limitSlider.on_change('value', limit_update)
    
    select = Select(title="ipm value:", value="ipm2", options=["ipm2", "ipm3"])
    select.on_change('value', switch)
    select.on_change('value', switch_background)
    
    startButton = Button(label='► Play')
    startButton.on_click(play_graph)
    
    updateButton = Button(label='Update', width=60)
    updateButton.on_click(update_background)
    
    plot = layout([[hvplot.state], 
                   widgetbox([limitSlider, select, updateButton, startButton], sizing_mode='stretch_both')])
    
    doc.title = "Reference Graph"
    doc.add_root(plot)

def new_data(*args, **kwargs):
    """
    Append data from subscribe into data containers
    
    """
    
    kwargs['in_value'].append(kwargs['value'])
    kwargs['in_time'].append(kwargs['timestamp'])

def launch_server():
    '''
    Launch a bokeh_server to plot a hextiles plot of ipm value over ebeam value
    and generate a background contour plot with updating scatter plot on top of it.
    Functionalities include a save button, clear button, pause button, and (buggy) ipm
    select drop down menu for the hextiles plot. Contour and scatter plot have an update
    button and select drop down.
    
    '''
    maxlen = 100000
    
    # Get data
    beam = FakeBeam()
    ipm2List = deque(maxlen=maxlen)
    ipm3List = deque(maxlen=maxlen)
    ebeamList = deque(maxlen=maxlen)
    ipm2TimeStamp = deque(maxlen=maxlen)
    ipm3TimeStamp = deque(maxlen=maxlen)
    ebeamTimeStamp = deque(maxlen=maxlen)
    
    # Subscribe to devices
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
            ),
            '/Time_History': partial(
                produce_timehistory,
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
    
    print('Opening Bokeh application on:')
    for entry in origins:
        print('\thttp://{}/'.format(entry))
    
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        print("terminating")
        server.io_loop.stop()
        
if __name__ == '__main__':
    launch_server()
