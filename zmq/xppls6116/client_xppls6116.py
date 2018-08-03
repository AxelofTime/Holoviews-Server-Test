import psana
import numpy as np
from mpidata import mpidata 
import RegDB.experiment_info

import sys
import os
abspath=(os.path.abspath(os.path.dirname(__file__))).replace('/examples','')
sys.path.append(abspath)
from smalldata_tools import defaultDetectors,epicsDetector,printMsg,detData,DetObject
from smalldata_tools import getUserData
from smalldata_tools import dropObject

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
            #dsname='shmem=XPP.0:stop=no' #this seems to be the case for x288
            dsname='shmem=psana.0:stop=no' #was for ls6116
            #dsname='shmem=monreqsrvpsana0.0:stop=no'
        else:
            dsname=args.dsname


    ds = psana.DataSource(dsname)
    ADU_per_photon=args.ADU_per_photon
    thresADU=args.thresADU
    epixname=args.areaDetName
    
    defaultDets = defaultDetectors(hutch)

    dets=[]
    #epix = DetObject(epixname ,ds.env(), run, common_mode=46)
    epix = DetObject(epixname ,ds.env(), run, common_mode=4)
    #epix = DetObject(epixname ,ds.env(), run, common_mode=0)
    epix.addPhotons(ADU_per_photon=ADU_per_photon, thresADU=thresADU, retImg=2, nphotMax=200)
    dets.append(epix)

    eventFilterNames=[]
    eventFilterNames.append('off')
    eventFilterNames.append('early')
    eventFilterNames.append('late')
    nImage=[]
    i0Sum=[]
    image=[]
    for filter in eventFilterNames:
        i0Sum.append(0.)
        nImage.append(0)
        image.append(np.zeros([99,99]))

    import time
    time0=time.time()
    for nevent,evt in enumerate(ds.events()):
        if nevent == args.noe : break
        if args.exprun.find('shmem')<0:
            if nevent%(size-1)!=rank-1: continue # different ranks look at different events
        #print 'pass here: ',nevent, rank, nevent%(size-1)
        defData = detData(defaultDets, evt)

        #event selection.
        
        #check that all required detectors are ok.
        if defData['damage']['ipm2'] < 1:
            continue
        if defData['damage']['evr0'] < 1:
            continue
        if defData['damage'][epixname] < 1:
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

        #now select good quality events.
        xray = defData['lightStatus']['xray']
        laser = defData['lightStatus']['laser']
        ipm2Sum = defData['ipm2']['sum']
        #
        try:
            lasDelay = defData['enc']['lasDelay']
        except:
            lasDelay = (np.random.rand(1)*-0.1)*10.
        try:
            ttCorr = defData['tt']['ttCorr']
            ttAmpl = defData['tt']['AMPL']
        except:
            ttAmpl=99.
            ttCorr=0.

        delay = ttCorr+lasDelay
        if xray < 1:
            continue

        if ipm2Sum < float(args.ipm2_min):
            continue
        if ttAmpl < float(args.ttampl_min):
            continue

        #pick event for certain categories.
        eventFilter=[]        
        eventFilter.append(laser == 0)
        eventFilter.append( (delay < args.tt_early_max) and (laser > 0) )
        try:
            eventFilter.append(( (delay > args.tt_late_min ) and (delay < args.tt_late_max ) and (laser > 0) )[0])
        except:
            try:
                eventFilter.append(( (delay > args.tt_late_min ) and (delay < args.tt_late_max ) and (laser > 0) ))
            except:
                print 'late selection broken'
                eventFilter.append(False)

        #skip events that do not pass any filter
        if np.array(eventFilter).sum()==0:
            continue
        
        #only now bother to deal with detector data to save time. 
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
                #print 'DEBUG: ',userDict[det._name].keys()
            except:
                pass
        
        #now sum the data for the defined classes of events.
        img = userDict[epixname]['photon_img']
        for iFilter,passFilter in enumerate(eventFilter):
            if passFilter:
                i0Sum[iFilter]+= ipm2Sum
                nImage[iFilter]+= 1
                if image[iFilter].shape != img.shape:
                    image[iFilter] = img
                else:
                    image[iFilter] += img

        # send mpi data object to master when desired
        if ((nevent)%20 == 0): #not sure how this is supposed to work...
            #print 'send data, looked at %d events, total ~ %d, run time %g, in rank %d '%(nevent, nevent*(size-1), (time.time()-time0),rank)
            if rank==1 and nevent>0:
                print 'send data, looked at %d events/rank, total ~ %d, run time %g, approximate rate %g'%(nevent, nevent*(size-1), (time.time()-time0), nevent*(size-1)/(time.time()-time0))
            evt_ts = evt.get(psana.EventId).time()
            md=mpidata()
            for name,i0,fimg,nImg in zip(eventFilterNames, i0Sum, image, nImage):
                md.addarray('img_%s'%name,fimg)
                md.addarray('i0_%s'%name,np.array(i0))
                md.addarray('n_%s'%name,np.array(nImg))
            md.addarray('nEvts',np.array([nevent]))
            md.addarray('evt_ts',np.array(evt_ts))
            md.send()
            #now reset.
            nImage=[]
            i0Sum=[]
            image=[]
            for i in range(len(eventFilter)):
                nImage.append(0)
                i0Sum.append(0.)
                image.append(np.zeros([99,99]))                

    #should be different for shared memory. Reset image&i0 I assume as default behavior. Copies for continued sums?
    md.endrun()	
