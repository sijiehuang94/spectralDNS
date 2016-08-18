__author__ = "Mikael Mortensen <mikaem@math.uio.no> and Diako Darian <diako.darian@mn.uio.no>"
__date__ = "2014-11-07"
__copyright__ = "Copyright (C) 2014-2016 " + __author__
__license__  = "GNU Lesser GPL version 3 or any later version"

from .spectralinit import *
from NS2D import get_curl, get_velocity, get_pressure

def setup():
    """Set up context for Bq2D solver"""

    FFT = get_FFT(params)
    float, complex, mpitype = datatypes(params.precision)    
    
    # Mesh variables
    X = FFT.get_local_mesh()
    K = FFT.get_scaled_local_wavenumbermesh()
    K2 = np.sum(K*K, 0, dtype=float)
    K_over_K2 = K.astype(float) / np.where(K2==0, 1, K2).astype(float)
    
    # Solution variables
    Ur     = empty((3,) + FFT.real_shape(), dtype=float)
    Ur_hat = empty((3,) + FFT.complex_shape(), dtype=complex)
    P      = empty(FFT.real_shape(), dtype=float)
    P_hat  = empty(FFT.complex_shape(), dtype=complex)
    curl   = empty(FFT.real_shape(), dtype=float)
    
    # Create views into large data structures
    rho     = Ur[2]
    rho_hat = Ur_hat[2]
    U       = Ur[:2] 
    U_hat   = Ur_hat[:2]
    
    # Primary variable
    u = Ur_hat

    # RHS and work arrays
    dU     = empty((3,) + FFT.complex_shape(), dtype=complex)
    work = work_arrays()
    
    hdf5file = HDF5Writer({"U":U[0], "V":U[1], "rho":rho, "P":P},
                          chkpoint={'current':{'U':Ur, 'P':P}, 'previous':{}},
                          filename="Bq2D.h5")
    
    return config.ParamsBase(locals())

class NS2DWriter(HDF5Writer):
    def update_components(self, Ur, Ur_hat, P, P_hat, FFT, **context):
        """Transform to real data before storing the solution"""
        for i in range(3):
            Ur[i] = FFT.ifft2(Ur_hat[i], Ur[i])
        P = FFT.ifft2(P_hat, P)

def get_rho(Ur, Ur_hat, FFT, **context):
    Ur[2] = FFT.ifft2(Ur_hat[2], Ur[2])
    return Ur[2]

@optimizer
def add_pressure_diffusion(rhs, ur_hat, P_hat, K_over_K2, K, K2, nu, Ri, Pr):
    u_hat = ur_hat[:2]
    rho_hat = ur_hat[2]
    
    # Compute pressure (To get actual pressure multiply by 1j)
    P_hat  = np.sum(rhs[:2]*K_over_K2, 0, out=P_hat)
    
    P_hat -= Ri*rho_hat*K_over_K2[1]
    
    # Add pressure gradient
    rhs[:2] -= P_hat*K

    # Add contribution from diffusion                      
    rhs[0] -= nu*K2*u_hat[0]
    rhs[1] -= (nu*K2*u_hat[1] + Ri*rho_hat)
    rhs[2] -= nu * K2 * rho_hat/Pr
    return rhs

def getConvection(convection):
    """Return function used to compute nonlinear term"""
    if convection in ("Standard", "Divergence", "Skewed"):

        raise NotImplementedError

    elif convection == "Vortex":

        def Conv(rhs, ur_hat, work, FFT, K):
            ur_dealias = work[((3,)+FFT.work_shape(params.dealias), float, 0)]
            curl_dealias = work[(FFT.work_shape(params.dealias), float, 0)]
            F_tmp = work[(rhs, 0)]
            
            for i in range(3):
                ur_dealias[i] = FFT.ifft2(ur_hat[i], ur_dealias[i], params.dealias)
                
            u_dealias = ur_dealias[:2]
            rho_dealiased = ur_dealias[2]

            F_tmp[0] = cross2(F_tmp[0], K, ur_hat[:2])
            curl_dealias = FFT.ifft2(F_tmp[0], curl_dealias, params.dealias)
            rhs[0] = FFT.fft2(u_dealias[1]*curl_dealias, rhs[0], params.dealias)
            rhs[1] = FFT.fft2(-u_dealias[0]*curl_dealias, rhs[1], params.dealias)
            
            F_tmp[0] = FFT.fft2(u_dealias[0]*rho_dealiased, F_tmp[0], params.dealias)
            F_tmp[1] = FFT.fft2(u_dealias[1]*rho_dealiased, F_tmp[1], params.dealias)
            rhs[2] = -1j*(K[0]*F_tmp[0]+K[1]*F_tmp[1])

            return rhs

    return Conv

def ComputeRHS(rhs, ur_hat, work, FFT, K, K2, K_over_K2, P_hat, **context):
    
    rhs = conv(rhs, ur_hat, work, FFT, K)
    
    rhs = add_pressure_diffusion(rhs, ur_hat, P_hat, K_over_K2, K, K2, params.nu, params.Ri, params.Pr)
    
    return rhs
