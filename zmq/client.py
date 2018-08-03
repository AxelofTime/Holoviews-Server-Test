import psana
import numpy as np
from mpidata import mpidata 
import RegDB.experiment_info

import sys
import os
from smalldata_tools import defaultDetectors,epicsDetector,printMsg,detData,DetObject
from smalldata_tools import getUserData
from smalldata_tools import dropObject
from smalldata_tools import ipmDetector
from smalldata_tools import ebeamDetector
##from SmallDataDefaultDetector import ebeamDetector

from mpi4py import MPI
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

def runclient(args):
    if args.exprun.find('shmem')<0:
        #get last run from experiment to extract calib info in DetObject
        dsname = args.exprun+':smd'
        run=int(args.exprun.split('run=')[-1])
        hutch=args.exprun.split(':')[0].replace('exp=','')[0:3]
    else: #shared memory.
        hutches=['amo','sxr','xpp','xcs','mfx','cxi','mec']
        import socket
        hostname=socket.gethostname()
        for ihutch in hutches:
            if hostname.find(ihutch)>=0:
                hutch=ihutch
                break
        expname=RegDB.experiment_info.active_experiment(hutch.upper())[1]
        run=int(RegDB.experiment_info.experiment_runs(hutch.upper(),exper=expname)[-1]['num'])
        calibdir = '/reg/d/psdm/%s/%s/calib'%(hutch,expname)
        psana.setOption('psana.calib-dir',calibdir)

        if args.exprun=='shmem':
            dsname='shmem=psana.0:stop=no' #was for ls6116
        else:
            dsname=args.dsname

    ds = psana.DataSource(dsname)
    defaultDets = defaultDetectors(hutch)
    defaultDets.append(ebeamDetector('EBeam','ebeam'))
    dets=[] #this list is for user data and ill initially not be used.

    import time
    time0=time.time()
    timeLastEvt=time0
    #slow down code when playing xtc files to look like real data
    timePerEvent=(1./120.)*(size-1)#time one event should take so that code is running 120 Hz


    sendFrequency=20 #send whenever rank has seen x events
    #vars_to_send=['event_time','ipm2__sum','ebeam__L3Energy']
    #vars_to_send.append(['tt__FLTPOSPS','tt__AMPL'])
    vars_to_send=[]

    masterDict={}
    for nevent,evt in enumerate(ds.events()):
        if nevent == args.noe : break
        if args.exprun.find('shmem')<0:
            if nevent%(size-1)!=rank-1: continue # different ranks look at different events
        #print 'pass here: ',nevent, rank, nevent%(size-1)
        defData = detData(defaultDets, evt)

        ###
        #event selection.
        ###
        #check that all required detectors are ok - this should ensure that we don't need to do any fancy event matching/filling at the cost of losing events.
        if 'ipm2' in defData.keys() and defData['damage']['ipm2'] < 1:
            continue
        if 'ipm5' in defData.keys() and defData['damage']['ipm5'] < 1:
            continue
        if defData['damage']['evr0'] < 1:
            continue

        try:
            if defData['damage']['tt'] < 1:
                continue
        except:
            pass

        try:
            if defData['damage']['enc'] < 1:
                continue
        except:
            pass
        
        #only now bother to deal with detector data to save time. 
        #for now, this will be empty and we will only look at defalt data
        userDict = {}
        for det in dets:
            try:
                #this should be a plain dict. Really.
                det.evt = dropObject()
                det.getData(evt)
                det.processDetector()
                userDict[det._name]=getUserData(det)
                try:
                    envData=getUserEnvData(det)
                    if len(envData.keys())>0:
                        userDict[det._name+'_env']=envData
                except:
                    pass
            except:
                pass
        

        #here we should append the current dict to a dict that will hold a subset of events.
        for key in defData:
            if isinstance(defData[key], dict):
                for skey in defData[key].keys():
                    if isinstance(defData[key][skey], dict):
                        print 'why do I have this level of dict?', key, skey, defData[key][skey].keys()
                        continue
                    varname_in_masterDict = '%s__%s'%(key, skey)
                    if len(vars_to_send)>0 and varname_in_masterDict not in vars_to_send:
                        continue
                    if varname_in_masterDict not in masterDict.keys():
                        masterDict[varname_in_masterDict] = [defData[key][skey]]
                    else:
                        masterDict[varname_in_masterDict].append(defData[key][skey])
            else:
                if len(vars_to_send)>0 and key not in vars_to_send:
                    continue
                if key not in masterDict.keys():
                    masterDict[key]=[defData[key]]
                else:
                    masterDict[key].append(defData[key])
        if 'event_time' not in masterDict.keys():
            masterDict['event_time'] = [evt.get(psana.EventId).time()]
        else:
            masterDict['event_time'].append(evt.get(psana.EventId).time())

        #make this run at 120 Hz - slow down if necessary
        # send mpi data object to master when desired
        #not sure how this is supposed to work...
        if len(masterDict['event_time'])%sendFrequency == 0:
            timeNow = time.time()
            if (timeNow - timeLastEvt) < timePerEvent*sendFrequency:
                time.sleep(timePerEvent*sendFrequency-(timeNow - timeLastEvt))
                timeLastEvt=time.time()
            #print 'send data, looked at %d events, total ~ %d, run time %g, in rank %d '%(nevent, nevent*(size-1), (time.time()-time0),rank)
            if rank==1 and nevent>0:
                if args.exprun.find('shmem')<0:
                    print 'send data, looked at %d events/rank, total ~ %d, run time %g, approximate rate %g from rank %d'%(nevent, nevent*(size-1), (time.time()-time0), nevent*(size-1)/(time.time()-time0), rank)
                else:
                    print 'send data, looked at %d events/rank, total ~ %d, run time %g, approximate rate %g from rank %d'%(nevent, nevent*(size-1), (time.time()-time0), nevent/(time.time()-time0), rank)
            md=mpidata()
            #I think add a list of keys of the data dictionary to the client.
            md.addarray('nEvts',np.array([nevent]))
            md.addarray('send_timeStamp', np.array(evt.get(psana.EventId).time()))
            for key in masterDict.keys():
                md.addarray(key,np.array(masterDict[key]))
            md.send()

            #now reset the local dictionay/lists.
            masterDict={}

    #should be different for shared memory. R
    try:
        md.endrun()	
        print 'call md.endrun from rank ',rank
    except:
        print 'failed to call md.endrun from rank ',rank
        pass
