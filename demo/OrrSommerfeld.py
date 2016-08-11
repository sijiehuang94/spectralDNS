"""Orr-Sommerfeld"""
from spectralDNS import config, get_solver
from OrrSommerfeld_eig import OrrSommerfeld
from numpy import dot, real, pi, cos, vstack, flipud, hstack, floor, exp, sum, zeros, arange, imag, sqrt, array, zeros_like, allclose
from mpiFFT4py import dct
from scipy.fftpack import ifft
import matplotlib.pyplot as plt
import warnings
import matplotlib.cbook
warnings.filterwarnings("ignore",category=matplotlib.cbook.mplDeprecation)

eps = 1e-5
def initOS(OS, U, X, t=0.):
    for i in range(U.shape[1]):
        x = X[0, i, 0, 0]
        OS.interp(x)
        for j in range(U.shape[2]):
            y = X[1, i, j, 0]
            v = (1-x**2) + eps*dot(OS.f, real(OS.dphidy*exp(1j*(y-OS.eigval*t))))
            u = -eps*dot(OS.f, real(1j*OS.phi*exp(1j*(y-OS.eigval*t))))  
            U[0, i, j, :] = u
            U[1, i, j, :] = v
    U[2] = 0

OS, e0 = None, None
def initialize(U, U_hat, U_hat0, solvePressure, H_hat1, FST,
               ST, X, comm, rank, conv, TDMASolverD, params, work, **kw):
    global OS, e0
    OS = OrrSommerfeld(Re=params.Re, N=100)
    initOS(OS, U, X)
    
    if not params.solver in ("KMM", "KMMRK3"):
        for i in range(3):
            U_hat0[i] = FST.fst(U[i], U_hat0[i], ST)        
        for i in range(3):
            U[i] = FST.ifst(U_hat0[i], U[i], ST)
        for i in range(3):
            U_hat0[i] = FST.fst(U[i], U_hat0[i], ST)        
        H_hat1 = conv(H_hat1, U_hat0)
        e0 = 0.5*FST.dx(U[0]**2+(U[1]-(1-X[0]**2))**2, ST.quad)    

        initOS(OS, U, U_hat, X, t=params.dt)
        for i in range(3):
            U_hat[i] = FST.fst(U[i], U_hat[i], ST)        
        for i in range(3):
            U[i] = FST.ifst(U_hat[i], U[i], ST)
        for i in range(3):
            U_hat[i] = FST.fst(U[i], U_hat[i], ST)        

        conv2 = zeros_like(H_hat1)
        conv2 = conv(conv2, 0.5*(U_hat0+U_hat))  
        for j in range(3):
            conv2[j] = TDMASolverD(conv2[j])
        conv2 *= -1
        kw['P_hat'] = solvePressure(kw['P_hat'], conv2)

        kw['P'] = FST.ifst(kw['P_hat'], kw['P'], kw['SN'])
        U_hat0[:] = U_hat
        params.t = params.dt
        params.tstep = 1
        
    else:
        U_hat0[0] = FST.fst(U[0], U_hat0[0], kw['SB']) 
        for i in range(1, 3):
            U_hat0[i] = FST.fst(U[i], U_hat0[i], ST)        
        U[0] = FST.ifst(U_hat0[0], U[0], kw['SB'])
        for i in range(1, 3):
            U[i] = FST.ifst(U_hat0[i], U[i], ST)
        H_hat1 = conv(H_hat1, U_hat0)
        e0 = 0.5*FST.dx(U[0]**2+(U[1]-(1-X[0]**2))**2, ST.quad) 
        
        initOS(OS, U, X, t=params.dt)
        U_hat[0] = FST.fst(U[0], U_hat[0], kw['SB']) 
        for i in range(1, 3):
            U_hat[i] = FST.fst(U[i], U_hat[i], ST)        
        U[0] = FST.ifst(U_hat[0], U[0], kw['SB'])
        for i in range(1, 3):
            U[i] = FST.ifst(U_hat[i], U[i], ST)

        U_hat0[:] = U_hat
        params.t = params.dt
        params.tstep = 1
        kw['g'][:] = 0

def set_Source(Source, Sk, FST, ST, params, **kw):
    Source[:] = 0
    Source[1] = -2./params.Re
    Sk[:] = 0
    Sk[1] = FST.fss(Source[1], Sk[1], ST)
        
im1, im2, im3, im4 = (None, )*4        
def update(rank, X, U, comm, FST, ST, U_hat, work, params, **kw):
    
    # Use GL for postprocessing
    global im1, im2, im3, OS, e0
    if im1 is None and rank == 0 and params.plot_step > 0:
        plt.figure()
        im1 = plt.contourf(X[1,:,:,0], X[0,:,:,0], U[0,:,:,0], 100)
        plt.colorbar(im1)
        plt.draw()

        plt.figure()
        im2 = plt.contourf(X[1,:,:,0], X[0,:,:,0], U[1,:,:,0] - (1-X[0,:,:,0]**2), 100)
        plt.colorbar(im2)
        plt.draw()

        plt.figure()
        im3 = plt.quiver(X[1, :,:,0], X[0,:,:,0], U[1,:,:,0]-(1-X[0,:,:,0]**2), U[0,:,:,0])
        plt.draw()
        
        plt.pause(1e-6)
        globals().update(im1=im1, im2=im2, im3=im3)

    if (params.tstep % params.plot_step == 0 or
        params.tstep % params.compute_energy == 0):
        
        if "KMM" in params.solver:
            U[0] = FST.ifst(U_hat[0], U[0], kw['SB'])
            for i in range(1, 3):
                U[i] = FST.ifst(U_hat[i], U[i], ST)     
        else:
            for i in range(3):
                U[i] = FST.ifst(U_hat[i], U[i], ST)
    
    if params.tstep % params.plot_step == 0 and rank == 0 and params.plot_step > 0:
        im1.ax.clear()
        im1.ax.contourf(X[1, :,:,0], X[0, :,:,0], U[0, :, :, 0], 100) 
        im1.autoscale()
        im2.ax.clear()
        im2.ax.contourf(X[1, :,:,0], X[0, :,:,0], U[1, :, :, 0]-(1-X[0,:,:,0]**2), 100)         
        im2.autoscale()
        im3.set_UVC(U[1,:,:,0]-(1-X[0,:,:,0]**2), U[0,:,:,0])
        plt.pause(1e-6)

    if params.tstep % params.compute_energy == 0: 
        U_tmp = work[(U, 0)]
        U[0] = FST.ifst(U_hat[0], U[0], kw['SB'])
        for i in range(1, 3):
            U[i] = FST.ifst(U_hat[i], U[i], ST)     

        pert = (U[1] - (1-X[0]**2))**2 + U[0]**2
        e1 = 0.5*FST.dx(pert, ST.quad)
        exact = exp(2*imag(OS.eigval)*(params.t))
        initOS(OS, U_tmp, X, t=params.t)
        pert = (U[0] - U_tmp[0])**2 + (U[1]-U_tmp[1])**2
        e2 = 0.5*FST.dx(pert, ST.quad)
        
        #ST.quad = 'GL'
        #kw['SB'].quad = 'GL'
        #X[:] = FST.get_local_mesh(ST)
        #initOS(OS, U_tmp, F_tmp, X, t=0)
        #e00 = 0.5*energy(U_tmp[0]**2+(U_tmp[1]-(1-X[0]**2))**2, params.N, comm, rank, params.L)
        
        #U[0] = FST.ifst(U_hat[0], U[0], kw['SB'])
        #for i in range(1, 3):
            #U[i] = FST.ifst(U_hat[i], U[i], ST)             
        #pert = (U[1] - (1-X[0]**2))**2 + U[0]**2
        #e11 = 0.5*energy(pert, params.N, comm, rank, params.L, X[0,:,0,0])
        #initOS(OS, U_tmp, F_tmp, X, t=params.t)
        #pert = (U[0] - U_tmp[0])**2 + (U[1]-U_tmp[1])**2
        #e22 = 0.5*energy(pert, params.N, comm, rank, params.L, X[0,:,0,0])
        #ST.quad = 'GC'
        #kw['SB'].quad = 'GC'
        #X[:] = FST.get_local_mesh(ST)
        
        if rank == 0:
            print "Time %2.5f Norms %2.16e %2.16e %2.16e %2.16e" %(params.t, e1/e0, exact, e1/e0-exact, sqrt(e2))

def regression_test(U, U0, X, comm, rank, FST, U_hat, U_hat0, params, ST, **kw):
    global OS, e0
    pert = (U[1] - (1-X[0]**2))**2 + U[0]**2
    e1 = 0.5*FST.dx(pert, ST.quad)
    exact = exp(2*imag(OS.eigval)*params.t)
    if rank == 0:
        print "Computed error = %2.8e %2.8e " %(sqrt(abs(e1/e0-exact)), params.dt)
    #U0[:] = 0
    #initOS(OS, U0, X, t=params.t)
    #U[0] = FST.ifst(U_hat[0], U[0], kw['SB'])
    #for i in range(1, 3):
        #U[i] = FST.ifst(U_hat[i], U[i], kw['ST'])
    #pert = (U[0] - U0[0])**2 + (U[1]-U0[1])**2
    #e1 = 0.5*FST.dx(pert, kw['ST'].quad)
    #if rank == 0:
        #print "Computed error = %2.8e %2.8e " %(sqrt(e1), params.dt)

if __name__ == "__main__":
    config.update(
        {
        'Re': 8000.,
        'nu': 1./8000.,             # Viscosity
        'dt': 0.001,                 # Time step
        'T': 0.01,                   # End time
        'L': [2, 2*pi, 4*pi/3.],
        'M': [7, 5, 2]
        },  "channel"
    )
    config.channel.add_argument("--compute_energy", type=int, default=1)
    config.channel.add_argument("--plot_step", type=int, default=1)
    solver = get_solver(update=update, regression_test=regression_test, mesh="channel")    
    initialize(**vars(solver))
    set_Source(**vars(solver))	
    solver.solve()
    #s = solver
    #s.FST.padsize = 2.0
    #U0 = s.FST.get_workarray(((3,)+s.FST.real_shape_padded(), s.float), 0)
    #U0[0] = s.FST.ifst(s.U_hat[0], U0[0], s.SB, dealias="3/2-rule")
    #U0[1] = s.FST.ifst(s.U_hat[1], U0[1], s.ST, dealias="3/2-rule")
    #U0[2] = s.FST.ifst(s.U_hat[2], U0[2], s.ST, dealias="3/2-rule")
    
    
