import sys
import zmq
import traceback

import numpy as np
import holoviews as hv
import pandas as pd

from bokeh.layouts import layout, widgetbox, row, column
from bokeh.models import Button, Slider, Select, HoverTool, DatetimeTickFormatter
from bokeh.plotting import curdoc
from bokeh.io import output_file, save
from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from holoviews.streams import Buffer
from holoviews.core import util
import tables
from functools import partial
from collections import deque
import datetime

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


def my_partial(func, *args, **kwargs):
    def wrap(*args, **kwargs):
        return func(*args, **kwargs)
    return partial(wrap, *args, **kwargs)
    
class ClassTest:
    
    def __init__(self):
        self.switchButton = 'ipm2__sum'
        
        trial = pd.DataFrame({'time':[],'correlation':[]})
        self.b_timehistory = Buffer(trial, length=40000)
        print("3: " + str(self.b_timehistory.data.head(5)))
        
    def clear_buffer(self):

        data = pd.DataFrame({'time':[], 'correlation':[]})
        
        with util.disable_constant(self.b_timehistory):
            
            self.b_timehistory.data = self.b_timehistory.data.iloc[:0]

        self.b_timehistory.send(data)
        print("1: " + str(self.b_timehistory.data.head(5)))
    
    def produce_graphs(self, context, doc):

        port = 5006
        socket = context.socket(zmq.SUB)
        # MUST BE FROM SAME MACHINE, CHANGE IF NECESSARY!!!
        socket.connect("tcp://psanagpu114:%d" % port)
        socket.setsockopt(zmq.SUBSCRIBE, b"")

        # Change and use my_partial to make the code more clear
        
        b_scatter = Buffer(pd.DataFrame({'timetool': []}), length=40000)
        b_IpmAmp = Buffer(pd.DataFrame({'ipm':[]}), length=1000)
        #b_timehistory = Buffer(pd.DataFrame({'correlation':[]}), length=40000)

        hvScatter = hv.DynamicMap(
            hv.Points, streams=[b_scatter]).options(
            width=1000, finalize_hooks=[apply_formatter], xrotation=45).redim.label(
            index='Time in UTC')
        
        hvIpmAmp = hv.DynamicMap(
            hv.Scatter, streams=[b_IpmAmp]).options(
            width=500).redim.label(
            index='Timetool Data')
        
        hvTimeHistory = hv.DynamicMap(
            my_partial(hv.Scatter, kdims=['time', 'correlation']), streams=[self.b_timehistory]).options(
            width=500, finalize_hooks=[apply_formatter], xrotation=45).redim.label(
            time='Time in UTC')

        layout = (hvIpmAmp+hvTimeHistory+hvScatter).cols(2)
        hvplot = renderer.get_plot(layout)
        cb_id_scatter = None
        cb_id_amp_ipm = None
        cb_id_timehistory = None

        def push_data_scatter(buffer):

            timetool_d = deque(maxlen=1000000)
            timetool_t = deque(maxlen=1000000)

            if socket.poll(timeout=0):
                stuff = socket.recv_pyobj()
                timetool_d = stuff['tt__FLTPOS_PS']

                timeData = deque(maxlen=1000000)
                for time in stuff['event_time']:
                    num1 = str(time[0])
                    num2 = str(time[1])
                    fullnum = num1 + "." + num2
                    timeData.append(float(fullnum))
                timetool_t = timeData

            timeStuff = list(timetool_t)
            # Convert time to seconds so bokeh formatter can get correct datetime
            times = [1000*time for time in timeStuff]

            data = pd.DataFrame({'timestamp': times, 'timetool': timetool_d})
            data = data.set_index('timestamp')
            data.index.name = None
            buffer.send(data)
            #print("Scatter")
            
        def push_data_amp_ipm (buffer):
        
            timetool_d = deque(maxlen=1000000)
            ipm2_d = deque(maxlen=1000000)

            if socket.poll(timeout=0):
                stuff = socket.recv_pyobj()
                timetool_d = stuff['tt__AMPL']
                ipm2_d = stuff[self.switchButton]

            data = pd.DataFrame({'timetool': timetool_d, 'ipm': ipm2_d})
            data = data.set_index('timetool')
            data.index.name = None

            buffer.send(data)
            #print("Versus")
            
        def push_data_correlation_time_history(buffer):
        
            maxlen = 1000000
            timetool_d = deque(maxlen=maxlen)
            timetool_t = deque(maxlen=maxlen)
            ipm2_d = deque(maxlen=maxlen)

            if socket.poll(timeout=0):
                stuff = socket.recv_pyobj()
                timetool_d = stuff['tt__FLTPOS_PS']
                ipm2_d = stuff[self.switchButton]

                timeData = deque(maxlen=maxlen)
                for time in stuff['event_time']:
                    num1 = str(time[0])
                    num2 = str(time[1])
                    fullnum = num1 + "." + num2
                    timeData.append(float(fullnum))
                timetool_t = timeData

            timeStuff = list(timetool_t)
            # Convert time to seconds so bokeh formatter can get correct datetime
            times = [1000*time for time in timeStuff]

            data = pd.DataFrame({'timetool': timetool_d, 'ipm': ipm2_d})

            data_list = data['timetool'].rolling(window=120).corr(other=data['ipm'])

            final_df = pd.DataFrame({
                'time': times[119:], 
                'correlation': data_list[119:]
            })

            #final_df = final_df.set_index('time')
            #final_df.index.name = None
            #print(len(final_df))

            buffer.send(final_df)
            #print("1: " + str(final_df.columns))
            #print("Boop: " + str(final_df.head(5)))
            print("2: " + str(buffer.data.head(5)))
            #print("Corr")
        
        def switch(attr, old, new):
            """
            Update drop down menu value

            """
            
            # WARNING: Buffers don't seem to be clearing
            try:
                self.switchButton = select.value
                #print(type(self.b_timehistory.data))
                #print(self.b_timehistory.data.columns)
                #print(b_IpmAmp.data.iloc[:0].columns)
                
                #print("Meep: "+ str(self.b_timehistory.data.iloc[0]))
                #print("Size: " + str(len(self.b_timehistory.data)))
                self.clear_buffer()
                
                print("I worked!")
                
                #b_IpmAmp.clear()
                #b_timehistory.clear()
            except Exception as exc:
                traceback.print_exc(file=sys.stdout)
            print("Boop")

        select = Select(title='ipm value:', value='ipm2__sum', options=['ipm2__sum', 'tt__FLTPOS_PS'])
        #select = Select(title='ipm value:', value='ipm2__sum', options=['ipm2__sum', 'ipm3__sum'])
        select.on_change('value', switch)
        #select.on_change('value', resetGraph)
        
#         reset = Button(label='reset')
#         reset.on_click(resetGraph)
        
        cb_id_scatter = doc.add_periodic_callback(
            partial(push_data_scatter, 
                    buffer=b_scatter), 
            1000)
        
        cb_id_amp_ipm = doc.add_periodic_callback(
            partial(push_data_amp_ipm,
                    buffer=b_IpmAmp), 
            1000)

        cb_id_timehistory = doc.add_periodic_callback(
            partial(push_data_correlation_time_history, 
                    buffer=self.b_timehistory), 
            1000)

        plot = column(select, hvplot.state)
        doc.add_root(plot)
        
def make_document(context, doc):
    trial = ClassTest()
    
    trial.produce_graphs(context, doc)
    
def launch_server():
   
    context = zmq.Context()

    origins = ["localhost:{}".format(5000)]
    
    apps = {'/': Application(FunctionHandler(partial(make_document, context)))}
    server = Server(apps, port=5000)
    
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
