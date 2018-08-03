#!/bin/bash
#export LD_LIBRARY_PATH=/reg/neh/home/cpo/junk
#echo `hostname`
source /reg/g/psdm/etc/psconda.sh
cd /reg/d/psdm/xpp/xppls6116/results/snelson_test/smalldata_tools/examples
python mpi_driver.py shmem --ipm2_min 0.05 --ttampl_min -0.001 --ADU_per_photon 155

#parser.add_argument("--thresADU", help="fraction of ADU a photons candidate needs to have",default=0.9)
#parser.add_argument("--ADU_per_photon", help="ADU / photon",default=155)
#parser.add_argument("--ipm2_min", help="minimum ipm2",default=0.1)
#parser.add_argument("--ttampl_min", help="minimum TT amplitude",default=0.025)
#parser.add_argument("--tt_early_max", help="maximum laser-xray delay for early time",default=0.3)
#parser.add_argument("--tt_late_min", help="minimum laser-xray delay for late time",default=0.6)
#parser.add_argument("--tt_late_max", help="maximum laser-xray delay for late time",default=10.)
