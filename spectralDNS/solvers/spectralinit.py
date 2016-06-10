__author__ = "Mikael Mortensen <mikaem@math.uio.no>"
__date__ = "2014-11-07"
__copyright__ = "Copyright (C) 2014-2016 " + __author__
__license__  = "GNU Lesser GPL version 3 or any later version"

from mpi4py import MPI
import sys, cProfile
from numpy import *
from mpiFFT4py import slab_FFT, pencil_FFT, line_FFT, empty, zeros    # possibly byte-aligned zeros/empty
from spectralDNS.utilities import *
from spectralDNS.h5io import *
from spectralDNS.optimization import *
from spectralDNS.maths import *

comm = MPI.COMM_WORLD
num_processes = comm.Get_size()
rank = comm.Get_rank()

def get_FFT(params):
    if params.decomposition == 'slab':
        assert len(params.N) == 3
        assert len(params.L) == 3
        FFT = slab_FFT(params.N, params.L, MPI, params.precision, communication=params.communication, threads=params.threads)
        
    elif params.decomposition == 'pencil':
        assert len(params.N) == 3
        assert len(params.L) == 3
        FFT = pencil_FFT(params.N, params.L, MPI, params.precision, P1=params.Pencil_P1, 
                         method=params.Pencil_method, threads=params.threads,
                         alignment=params.Pencil_alignment)
            
    elif params.decomposition == 'line':
        assert len(params.N) == 2
        assert len(params.L) == 2
        FFT = line_FFT(params.N, params.L, MPI, params.precision)
    return FFT

def regression_test(**kw):
    pass

def update(**kw):
    pass

def additional_callback(**kw):
    pass

def set_source(Source, **kw):
    Source[:] = 0
    return Source
