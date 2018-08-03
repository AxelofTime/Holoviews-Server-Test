from mpi4py import MPI
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

from psmon import publish
import psmon.plots as psplt
import h5py
import numpy as np
from mpidata import mpidata 
from psmon import publish
from psmon.plots import Image, MultiPlot

def runmaster(nClients):
    myDict={}
    publish.init()
    while nClients > 0:
        # Remove client if the run ended
        md = mpidata()
        md.recv()
        if publish.get_reset_flag():
            myDict={}
            publish.clear_reset_flag()
        if md.small.endrun:
            nClients -= 1
        else:
            #try:
            #    print 'DEBUG: master: ', md.n_late, md.nEvts, myDict['n_late']
            #except:
            #    print 'DEBUG: master: ', md.n_late, md.nEvts
            for mds in md.small.arrayinfolist:
                if mds.name=='n_off':
                    if mds.name not in myDict:
                        myDict['n_off']=md.n_off
                    else:
                        myDict['n_off']+=md.n_off
                if mds.name=='n_early':
                    if mds.name not in myDict:
                        myDict['n_early']=md.n_early
                    else:
                        myDict['n_early']+=md.n_early
                if mds.name=='n_late':
                    if mds.name not in myDict:
                        myDict['n_late']=md.n_late
                    else:
                        myDict['n_late']+=md.n_late

                if mds.name=='i0_off':
                    if mds.name not in myDict:
                        myDict['i0_off']=md.i0_off
                    else:
                        myDict['i0_off']+=md.i0_off
                if mds.name=='i0_early':
                    if mds.name not in myDict:
                        myDict['i0_early']=md.i0_early
                    else:
                        myDict['i0_early']+=md.i0_early
                if mds.name=='i0_late':
                    if mds.name not in myDict:
                        myDict['i0_late']=md.i0_late
                    else:
                        myDict['i0_late']+=md.i0_late

                if mds.name=='img_off' and md.img_off.shape[0]!=99:
                    if mds.name not in myDict:
                        myDict['img_off']=md.img_off
                    else:
                        myDict['img_off']+=md.img_off
                if mds.name=='img_early' and md.img_early.shape[0]!=99:
                    if mds.name not in myDict:
                        myDict['img_early']=md.img_early
                    else:
                        myDict['img_early']+=md.img_early
                if mds.name=='img_late' and md.img_late.shape[0]!=99:
                    if mds.name not in myDict:
                        myDict['img_late']=md.img_late
                    else:
                        myDict['img_late']+=md.img_late
            #md.addarray('evt_ts',np.array(evt_ts))
            evt_ts_str = '%.4f'%(md.evt_ts[0] + md.evt_ts[1]/1e9)
            plot(myDict, evt_ts_str)

def plot(sumDict, event_ts_str):
    #print sumDict['n_off'], sumDict['n_early'], sumDict['n_late']

    #publish.local=True
    publish.plot_opts.palette='spectrum'
    multi_plot_data = MultiPlot(event_ts_str, 'normImg')
    multi_plot_dataDiff = MultiPlot(event_ts_str, 'normImgDiff')

    if 'img_off' in sumDict.keys():
        sumDict['img_off'] = sumDict['img_off'].astype(float)
    if 'img_early' in sumDict.keys():
        sumDict['img_early'] = sumDict['img_early'].astype(float)
    if 'img_late' in sumDict.keys():
        sumDict['img_late'] = sumDict['img_late'].astype(float)

    if sumDict['n_off']>0:
        #plotImgOffNorm = Image(0,'off_norm',sumDict['img_off']/sumDict['i0_off'])
        plotImgOffNorm = Image(0,'off_norm',sumDict['img_off']/sumDict['n_off'])
        multi_plot_data.add(plotImgOffNorm)
    if sumDict['n_early']>0:
        #plotImgEarlyNorm = Image(0,'early_norm',sumDict['img_early']/sumDict['i0_early'])
        plotImgEarlyNorm = Image(0,'early_norm',sumDict['img_early']/sumDict['n_early'])
        multi_plot_data.add(plotImgEarlyNorm)
    if sumDict['n_late']>0:
        #plotImgLateNorm = Image(0,'late_norm',sumDict['img_late']/sumDict['i0_late'])
        plotImgLateNorm = Image(0,'late_norm',sumDict['img_late']/sumDict['n_late'])
        multi_plot_data.add(plotImgLateNorm)
    #uncomment to see plots.
    if sumDict['n_early']>0 and sumDict['n_late']>0:
        publish.send('normImg', multi_plot_data)
        plotImgDiffT0 = Image(0,'late_early',sumDict['img_late']/sumDict['i0_late']-sumDict['img_early']/sumDict['i0_early'])
        multi_plot_dataDiff.add(plotImgDiffT0)

    if sumDict['n_off']>0 and sumDict['n_late']>0:
        plotImgDiffOff = Image(0,'late_off',sumDict['img_late']/sumDict['i0_late']-sumDict['img_off']/sumDict['i0_off'])
        multi_plot_dataDiff.add(plotImgDiffOff)

    if sumDict['n_early']>0 and sumDict['n_late']>0 and sumDict['n_off']>0:
        publish.send('normImgDiff', multi_plot_dataDiff)
