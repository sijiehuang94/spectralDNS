"""Orr-Sommerfeld"""
import pyfftw  # Hack because of https://github.com/pyFFTW/pyFFTW/issues/40
from spectralDNS import config, get_solver, solve
from OrrSommerfeld_shen import OrrSommerfeld
#from OrrSommerfeld_eig import OrrSommerfeld
from numpy import dot, real, pi, cos, exp, sum, zeros, arange, imag, sqrt, \
    array, zeros_like, log10
from numpy.linalg import norm
from mpiFFT4py import dct
from scipy.fftpack import ifft
import warnings

try:
    import matplotlib.pyplot as plt
    import matplotlib.cbook
    warnings.filterwarnings("ignore",category=matplotlib.cbook.mplDeprecation)

except ImportError:
    warnings.warn("matplotlib not installed")
    plt = None

#params.eps = 1e-9
#def initOS(OS, U, X, t=0.):
    #for i in range(U.shape[1]):
        #x = X[0, i, 0, 0]
        #OS.interp(x, 1)
        #for j in range(U.shape[2]):
            #y = X[1, i, j, 0]
            #v = (1-x**2) + config.params.eps*dot(OS.f, real(OS.dphidy*exp(1j*(y-OS.eigval*t))))
            #u = -config.params.eps*dot(OS.f, real(1j*OS.phi*exp(1j*(y-OS.eigval*t))))
            #U[0, i, j, :] = u
            #U[1, i, j, :] = v
    #U[2] = 0

def initOS(OS, U, X, t=0.):
    x = X[0, :, 0, 0]
    phi, dphidy = OS.interp(x, 1, same_mesh=False, verbose=False)
    for j in range(U.shape[2]):
        y = X[1, 0, j, 0]
        v = (1-x**2) + config.params.eps*real(dphidy*exp(1j*(y-OS.eigval*t)))
        u = -config.params.eps*real(1j*phi*exp(1j*(y-OS.eigval*t)))
        U[0, :, j, :] = u.repeat(U.shape[3]).reshape((len(x), U.shape[3]))
        U[1, :, j, :] = v.repeat(U.shape[3]).reshape((len(x), U.shape[3]))
    U[2] = 0

acc = zeros(1)
OS, e0 = None, None
def initialize(solver, context):
    global OS, e0
    params = config.params
    OS = OrrSommerfeld(Re=params.Re, N=context.N[0])
    OS.solve(False)
    U = context.U
    X = context.X
    FST = context.FST
    initOS(OS, U, X)

    U_hat = solver.set_velocity(**context)
    U = solver.get_velocity(**context)

    # Compute convection from data in context (i.e., context.U_hat and context.g)
    # This is the convection at t=0
    e0 = 0.5*FST.dx(U[0]**2+(U[1]-(1-X[0]**2))**2, context.ST.quad)
    acc[0] = 0.0

    if not params.solver == 'KMMRK3':
        # Initialize at t = dt
        context.H_hat1[:] = solver.get_convection(**context)
        initOS(OS, U, X, t=params.dt)
        U_hat = solver.set_velocity(**context)
        U = solver.get_velocity(**context)
        context.U_hat0[:] = U_hat
        params.t = params.dt
        params.tstep = 1
        e1 = 0.5*FST.dx(U[0]**2+(U[1]-(1-X[0]**2))**2, context.ST.quad)
        acc[0] += abs(e1/e0 - exp(2*imag(OS.eigval)*params.t))

    else:
        params.t = 0
        params.tstep = 0

    if not params.solver in ("KMM", "KMMRK3"):
        P_hat = solver.compute_pressure(**context)
        P = FST.ifst(P_hat, context.P, context.SN)

    else:
        context.g[:] = 0

def set_Source(Source, Sk, FST, ST, **kw):
    Source[:] = 0
    Source[1] = -2./config.params.Re
    Sk[:] = 0
    Sk[1] = FST.fss(Source[1], Sk[1], ST)

im1, im2, im3, im4 = (None, )*4
def update(context):

    c = context
    params = config.params
    solver = config.solver

    if (params.tstep % params.plot_step == 0 or
        params.tstep % params.compute_energy == 0):
        U = solver.get_velocity(**context)

    # Use GL for postprocessing
    global im1, im2, im3, OS, e0, acc
    if not plt is None:
        if im1 is None and solver.rank == 0 and params.plot_step > 0:
            plt.figure()
            im1 = plt.contourf(c.X[1,:,:,0], c.X[0,:,:,0], c.U[0,:,:,0], 100)
            plt.colorbar(im1)
            plt.draw()

            plt.figure()
            im2 = plt.contourf(c.X[1,:,:,0], c.X[0,:,:,0], c.U[1,:,:,0] - (1-c.X[0,:,:,0]**2), 100)
            plt.colorbar(im2)
            plt.draw()

            plt.figure()
            im3 = plt.quiver(c.X[1, :,:,0], c.X[0,:,:,0], c.U[1,:,:,0]-(1-c.X[0,:,:,0]**2), c.U[0,:,:,0])
            plt.draw()

            plt.pause(1e-6)

        if params.tstep % params.plot_step == 0 and solver.rank == 0 and params.plot_step > 0:
            im1.ax.clear()
            im1.ax.contourf(c.X[1, :,:,0], c.X[0, :,:,0], U[0, :, :, 0], 100)
            im1.autoscale()
            im2.ax.clear()
            im2.ax.contourf(c.X[1, :,:,0], c.X[0, :,:,0], U[1, :, :, 0]-(1-c.X[0,:,:,0]**2), 100)
            im2.autoscale()
            im3.set_UVC(U[1,:,:,0]-(1-c.X[0,:,:,0]**2), U[0,:,:,0])
            plt.pause(1e-6)

    if params.tstep % params.compute_energy == 0:
        U_tmp = c.work[(U, 0)]
        U = solver.get_velocity(**context)
        pert = (U[1] - (1-c.X[0]**2))**2 + U[0]**2
        e1 = 0.5*c.FST.dx(pert, c.ST.quad)
        exact = exp(2*imag(OS.eigval)*params.t)
        initOS(OS, U_tmp, c.X, t=params.t)
        pert = (U[0] - U_tmp[0])**2 + (U[1]-U_tmp[1])**2
        e2 = 0.5*c.FST.dx(pert, c.ST.quad)
        pert3 = (U[0] - U_tmp[0])**2
        e3 = 0.5*c.FST.dx(pert3, c.ST.quad)
        pert4 = (U[1]-U_tmp[1])**2
        e4 = 0.5*c.FST.dx(pert4, c.ST.quad)

        acc[0] += abs(e1/e0-exact)
        #acc[0] += e1/e0

        #ST.quad = 'GL'
        #kw['SB'].quad = 'GL'
        #X[:] = FST.get_local_mesh(ST)
        #initOS(OS, U_tmp, F_tmp, X, t=0)
        #e00 = 0.5*energy(U_tmp[0]**2+(U_tmp[1]-(1-X[0]**2))**2, params.N, comm, rank, params.L)
        #pert = (U[1] - (1-X[0]**2))**2 + U[0]**2
        #e11 = 0.5*energy(pert, params.N, comm, rank, params.L, X[0,:,0,0])
        #initOS(OS, U_tmp, F_tmp, X, t=params.t)
        #pert = (U[0] - U_tmp[0])**2 + (U[1]-U_tmp[1])**2
        #e22 = 0.5*energy(pert, params.N, comm, rank, params.L, X[0,:,0,0])
        #ST.quad = 'GC'
        #kw['SB'].quad = 'GC'
        #X[:] = FST.get_local_mesh(ST)

        if solver.rank == 0:
            print("Time %2.5f Norms %2.16e %2.16e %2.16e %2.16e %2.16e %2.16e" %(params.t, e1/e0, exact, e1/e0-exact, sqrt(e2)/params.eps, sqrt(e3)/params.eps, sqrt(e4)/params.eps))
            #print("Time %2.5f Norms %2.16e %2.16e %2.16e %2.16e" %(params.t, e1/e0, exact, e1/e0-exact, sqrt(sum(pert))))

def regression_test(context):
    global OS, e0
    params = config.params
    solver = config.solver
    U = solver.get_velocity(**context)
    U0 = context.work[(U, 0)]
    initOS(OS, U0, context.X, t=params.t)
    pert = (U[0] - U0[0])**2 + (U[1]-U0[1])**2
    e1 = 0.5*context.FST.dx(pert, context.ST.quad)
    if solver.rank == 0:
        assert sqrt(e1) < 1e-12

def refinement_test(context):
    global OS, e0, acc
    c = context
    params = config.params
    solver = config.solver
    U = solver.get_velocity(**context)
    pert = (U[1] - (1-c.X[0]**2))**2 + U[0]**2
    e1 = 0.5*c.FST.dx(pert, c.ST.quad)
    exact = exp(2*imag(OS.eigval)*params.t)
    #if solver.rank == 0:
        ##print("Computed error = %2.8e %2.8e " %((abs(e1/e0-exact)), params.dt))
        #trapz = (acc[0] - 0.5*abs(e1/e0-exact))*params.dt
        #print("Computed error = %2.8e %2.8e " %(abs(trapz), params.dt))
        #trapz = (acc[0] - 0.5*e1/e0)*params.dt
        #print trapz, 1./2./imag(OS.eigval)*(exact - 1)
        #print("Computed error = %2.8e %2.8e " %(abs(trapz - 1./2./imag(OS.eigval)*(exact - 1)), params.dt))

    U0 = c.work[(c.U, 0)]
    initOS(OS, U0, c.X, t=params.t)
    pert = (U[0] - U0[0])**2 + (U[1]-U0[1])**2
    e2 = 0.5*c.FST.dx(pert, c.ST.quad)
    #pert3 = (U[0] - U0[0])**2
    #e3 = 0.5*c.FST.dx(pert3, c.ST.quad)
    if solver.rank == 0:
        #print("Computed error = %2.8e %2.8e %2.8e" %(sqrt(e2)/config.params.eps, params.dt, params.eps))
        print(" %2d & %2.8e & %2.8e \\\ " %(-int(log10(params.eps)), sqrt(e2)/config.params.eps, e1/e0-exact))

if __name__ == "__main__":
    config.update(
        {
        'Re': 8000.,
        'nu': 1./8000.,             # Viscosity
        'dt': 0.001,                 # Time step
        'T': 0.01,                   # End time
        'L': [2, 2*pi, 4*pi/3.],
        'M': [7, 5, 1],
        'eps': 1e-7
        },  "channel"
    )
    config.channel.add_argument("--compute_energy", type=int, default=1)
    config.channel.add_argument("--plot_step", type=int, default=10)
    config.channel.add_argument("--refinement_test", type=bool, default=False)
    #solver = get_solver(update=update, regression_test=regression_test, mesh="channel")
    solver = get_solver(update=update, mesh="channel")
    if config.params.refinement_test:
        solver.regression_test = refinement_test

    context = solver.get_context()
    initialize(solver, context)
    set_Source(**context)
    solve(solver, context)
    #s = solver
    #s.FST.padsize = 2.0
    #U0 = s.FST.get_workarray(((3,)+s.FST.real_shape_padded(), s.float), 0)
    #U0[0] = s.FST.ifst(s.U_hat[0], U0[0], s.SB, dealias="3/2-rule")
    #U0[1] = s.FST.ifst(s.U_hat[1], U0[1], s.ST, dealias="3/2-rule")
    #U0[2] = s.FST.ifst(s.U_hat[2], U0[2], s.ST, dealias="3/2-rule")
    #config.params.eps = 1e-6
    config.params.verbose=False
    print "Test"
    solver.update = lambda x: None
    for eps in [1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9, 1e-10, 1e-11, 1e-12]:
        config.params.eps = eps
        initialize(solver, context)
        solve(solver, context)
