__author__ = "Mikael Mortensen <mikaem@math.uio.no>"
__date__ = "2014-11-19"
__copyright__ = "Copyright (C) 2014 " + __author__
__license__  = "GNU Lesser GPL version 3 or any later version"

__all__ = ['dct', 'fft', 'ifft', 'fft2', 'ifft2', 'fftn', 'ifftn',
           'rfft', 'irfft', 'rfft2', 'irfft2', 'rfftn', 'irfftn', 
           'fftfreq', 'empty', 'zeros']

from numpy import empty, zeros, iscomplexobj
from numpy.fft import fftfreq, fft, ifft, fftn, ifftn, rfft, irfft, rfft2, irfft2, rfftn, irfftn, fft2, ifft2
from scipy.fftpack import dct

try:
    import pyfftw
    nzeros = zeros
    nthreads = 1
    def empty(N, dtype=float, bytes=16):
        return pyfftw.n_byte_align_empty(N, bytes, dtype=dtype)

    def zeros(N, dtype=float, bytes=16):
        return pyfftw.n_byte_align(nzeros(N, dtype=dtype), bytes)
    
    ## Monkey patches for fft
    #ifft = pyfftw.interfaces.numpy_fft.ifft
    #fft = pyfftw.interfaces.numpy_fft.fft
    #fft2 = pyfftw.interfaces.numpy_fft.fft2
    #ifft2 = pyfftw.interfaces.numpy_fft.ifft2
    #irfft = pyfftw.interfaces.numpy_fft.irfft
    #rfft = pyfftw.interfaces.numpy_fft.rfft
    #rfft2 = pyfftw.interfaces.numpy_fft.rfft2
    #irfft2 = pyfftw.interfaces.numpy_fft.irfft2
    #ifftn = pyfftw.interfaces.numpy_fft.ifftn
    #fftn = pyfftw.interfaces.numpy_fft.fftn
    #irfftn = pyfftw.interfaces.numpy_fft.irfftn
    #rfftn = pyfftw.interfaces.numpy_fft.rfftn

    dct_object    = {}
    fft_object    = {}
    ifft_object   = {}
    fft2_object   = {}
    ifft2_object  = {}
    fftn_object   = {}
    ifftn_object  = {}
    irfft_object  = {}
    irfftn_object = {}
    irfft2_object = {}
    rfft2_object  = {}
    rfft_object   = {}
    rfftn_object  = {}
    if hasattr(pyfftw.builders, "dchjt"):
        def dct(a, type=2, axis=0):
            global dct_object
            if not (a.shape, type) in dct_object:
                b = a.copy()
                dct_object[(a.shape, type)] = (pyfftw.builders.dct(b, axis=axis, type=type), a.copy())
                
            dobj, c = dct_object[(a.shape, type)]
            in_array = dobj.get_input_array()
            if iscomplexobj(a):
                in_array[:] = a.real
                c.real[:] = dobj()
                in_array[:] = a.imag
                c.imag[:] = dobj()            

            else:
                in_array[:] = a
                c[:] = dobj()
            return c
        
    else:
        dct1 = pyfftw.interfaces.scipy_fftpack.dct
        def dct(x, type=2, axis=0):
            if iscomplexobj(x):
                xreal = dct1(x.real, type=type, axis=axis)
                ximag = dct1(x.imag, type=type, axis=axis)
                return xreal + ximag*1j
            else:
                return dct1(x, type=type, axis=axis)
        
    def ifft(a, axis=None):
        global ifft_object
        if not a.shape in ifft_object:
            b = a.copy()
            ifft_object[a.shape] = pyfftw.builders.ifft(b, axis=axis)    
            
        in_array = ifft_object[a.shape].get_input_array()
        in_array[:] = a
        return ifft_object[a.shape]()

    def ifft2(a, axes=None):
        global ifft2_object
        if not a.shape in ifft2_object:
            b = a.copy()
            ifft2_object[a.shape] = pyfftw.builders.ifft2(b, axes=axes)    
            
        in_array = ifft2_object[a.shape].get_input_array()
        in_array[:] = a
        return ifft2_object[a.shape]()

    def ifftn(a, axes=None):
        global ifftn_object
        if not a.shape in ifftn_object:
            b = a.copy()
            ifftn_object[a.shape] = pyfftw.builders.ifftn(b, axes=axes)    
            
        in_array = ifftn_object[a.shape].get_input_array()
        in_array[:] = a
        return ifftn_object[a.shape]()

    def irfft(a, axis=None):
        global irfft_object
        if not a.shape in irfft_object:
            b = a.copy()
            irfft_object[a.shape] = pyfftw.builders.irfft(b, axis=axis)
            
        in_array = irfft_object[a.shape].get_input_array()
        in_array[:] = a
        return irfft_object[a.shape]()

    def irfft2(a, axes=None):
        global irfft2_object
        if not a.shape in irfft2_object:
            b = a.copy()
            irfft2_object[a.shape] = pyfftw.builders.irfft2(b, axes=axes)
            
        in_array = irfft2_object[a.shape].get_input_array()
        in_array[:] = a
        return irfft2_object[a.shape]()

    def irfftn(a, axes=None):
        global irfftn_object
        if not a.shape in irfftn_object:
            b = a.copy()
            irfftn_object[a.shape] = pyfftw.builders.irfftn(b, axes=axes)
            
        in_array = irfftn_object[a.shape].get_input_array()
        in_array[:] = a
        return irfftn_object[a.shape]()
    
    def fft(a, axis=None):
        global fft_object
        if not a.shape in fft_object:
            b = a.copy()
            fft_object[a.shape] = pyfftw.builders.fft(b, axis=axis)
        
        in_array = fft_object[a.shape].get_input_array()
        in_array[:] = a
        return fft_object[a.shape]()

    def fft2(a, axes=None):
        global fft2_object
        if not a.shape in fft2_object:
            b = a.copy()
            fft2_object[a.shape] = pyfftw.builders.fft2(b, axes=axes)
        
        in_array = fft2_object[a.shape].get_input_array()
        in_array[:] = a
        return fft2_object[a.shape]()

    def fftn(a, axes=None):
        global fftn_object
        if not a.shape in fftn_object:
            b = a.copy()
            fftn_object[a.shape] = pyfftw.builders.fftn(b, axes=axes)
        
        in_array = fftn_object[a.shape].get_input_array()
        in_array[:] = a
        return fftn_object[a.shape]()

    def rfft(a, axis=None):
        global rfft_object
        if not a.shape in rfft_object:
            b = a.copy()
            rfft_object[a.shape] = pyfftw.builders.rfft(b, axis=axis)
            
        in_array = rfft_object[a.shape].get_input_array()
        in_array[:] = a        
        return rfft_object[a.shape]()

    def rfft2(a, axes=None):
        global rfft2_object
        if not a.shape in rfft2_object:
            b = a.copy()
            rfft2_object[a.shape] = pyfftw.builders.rfft2(b, axes=axes)
            
        in_array = rfft2_object[a.shape].get_input_array()
        in_array[:] = a        
        return rfft2_object[a.shape]()

    def rfftn(a, axes=None):
        global rfftn_object
        if not a.shape in rfftn_object:
            b = a.copy()
            rfftn_object[a.shape] = pyfftw.builders.rfftn(b, axes=axes)
            
        in_array = rfftn_object[a.shape].get_input_array()
        in_array[:] = a        
        return rfftn_object[a.shape]()

except:    
    print Warning("Install pyfftw, it is much faster than numpy fft")
