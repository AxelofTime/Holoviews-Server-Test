from mpi4py import MPI
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

import numpy as np
from mpidata import mpidata 
import zmq
import random
import sys
import time

# Only make socket and connection once

def runmaster(nClients):
    global socket
    port = "5006"
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:%s" % port)

    myDict={}
    while nClients > 0:
        # Remove client if the run ended
        md = mpidata()
        md.recv()
        ##ideally, there is a reset option from the bokeh server, but we can make this 
        ##optional & reset on run boundaries instead/in addition.
        ##can be ignored while testing on recorded runs.
        #if publish.get_reset_flag():
        #    myDict={}
        #    publish.clear_reset_flag()
        if md.small.endrun:
            nClients -= 1
        else:
            #    print 'DEBUG: master: ', md.n_late, md.nEvts   
            #this here is where we append the lists in the dictionary we got from the clients to a big master dict.

            for mds in md.small.arrayinfolist:
                #I remember: I do not know how to access the data from the"md" object using its name as a string.
                #Really need to figure this one out, if I know how it would like like
                if mds.name not in myDict.keys():
                    myDict[mds.name]=getattr(md, mds.name)
                else:
                    myDict[mds.name]=np.append(myDict[mds.name], getattr(md, mds.name), axis=0)

            #md.addarray('evt_ts',np.array(evt_ts))
            evt_ts_str = '%.4f'%(md.send_timeStamp[0] + md.send_timeStamp[1]/1e9)
            #here we will send the dict (or whatever we make this here) to the plots.
            dataToZMQ(myDict, evt_ts_str)
            print("Send")


def dataToZMQ(sumDict, event_ts_str):
    #here we will issue the ZMQ send command. I am not sure what format the data should have here.
    
    #placeholder code
    #print 'DEBUG keys: ',sumDict['event_time'].shape, sumDict.keys()

    socket.send_pyobj(sumDict)

#
# the app to go with this is like the code written for EPICS, except that the data going into the stream/buffer is not event built from EPICS, but instead received from ZMQ.
#
