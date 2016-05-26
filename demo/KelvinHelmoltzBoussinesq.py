from spectralDNS import config, get_solver
import matplotlib.pyplot as plt
from numpy import zeros, exp, sum, pi, exp, sin, cos, tanh

def initialize(X, U, Ur, Ur_hat, rho, FFT, float, params, **kwargs):
    
    N = params.N
    Um = 0.5*(params.U1 - params.U2)
    U[1] = params.A*sin(2*X[0])
    #U[0, :, :N/4] = params.U1 - Um*exp((X[1,:, :N/4] - 0.5*pi)/params.delta) 
    #U[0, :, N/4:N/2] = params.U2 + Um*exp(-1.0*(X[1, :, N/4:N/2] - 0.5*pi)/params.delta) 
    #U[0, :, N/2:3*N/4] = params.U2 + Um*exp((X[1, :, N/2:3*N/4] - 1.5*pi)/params.delta) 
    #U[0, :, 3*N/4:] = params.U1 - Um*exp(-1.0*(X[1, :, 3*N/4:] - 1.5*pi)/params.delta)
    
    #rho[:, :N/2] = tanh((X[1][:, :N/2]-(0.5*pi))/params.delta)
    #rho[:, N/2:] =-tanh((X[1][:, N/2:]-(1.5*pi))/params.delta)
                
    rho0 = 0.5*(params.rho1 + params.rho2)
    U[0, :, :N[1]/2] = tanh((X[1, :, :N[1]/2] -0.5*pi)/params.delta)
    U[0, :, N[1]/2:] = -tanh((X[1, :, N[1]/2:]-1.5*pi)/params.delta)
    rho[:, :N[1]/2] = 2.0 + tanh((X[1, :, :N[1]/2] -0.5*pi)/params.delta)
    rho[:, N[1]/2:] = 2.0 -tanh((X[1, :, N[1]/2:]-1.5*pi)/params.delta) 
    rho -= rho0
    
    for i in range(3):
        Ur_hat[i] = FFT.fft2(Ur[i], Ur_hat[i]) 

im, im2 = None, None
def update(comm, rank, rho, curl, K, FFT, U_hat, U, params,
           P_hat, P, hdf5file, float64, rho_hat, **kwargs):
    global im, im2
    
    dx, L, N = params.dx, params.L, params.N
    if (hdf5file.check_if_write(params) or (params.tstep % params.plot_result == 0 
        and params.plot_result > 0)):
        P = FFT.ifft2(P_hat*1j, P)
        curl = FFT.ifft2(1j*K[0]*U_hat[1]-1j*K[1]*U_hat[0], curl)
        
    if params.tstep == 1 and params.plot_result > 0:
        fig, ax = plt.subplots(1, 1)
        fig.suptitle('Density', fontsize=20)
        ax.set_xlabel('x')
        ax.set_ylabel('y')

        im = ax.imshow(zeros((N[0], N[1])),cmap=plt.cm.bwr, extent=[0, L[0], 0, L[1]])
        plt.colorbar(im)
        plt.draw() 

        fig2, ax2 = plt.subplots(1,1)
        fig2.suptitle('Vorticity', fontsize=20)   
        ax2.set_xlabel('x')
        ax2.set_ylabel('y')

        im2 = ax2.imshow(zeros((N[0], N[1])),cmap=plt.cm.bwr, extent=[0, L[0], 0, L[1]])
        plt.colorbar(im2)
        plt.draw()
        globals().update(dict(im=im, im2=im2))

    if params.tstep % params.plot_result == 0 and params.plot_result > 0:
        im.set_data(rho[:, :].T)
        im.autoscale()
        plt.pause(1e-6)
        im2.set_data(curl[:,:].T)
        im2.autoscale()
        plt.pause(1e-6)
        if rank == 0:
            print params.tstep

    if hdf5file.check_if_write(params):
        hdf5file.write(params)           

    if params.tstep % params.compute_energy == 0:
        kk = comm.reduce(sum(U.astype(float64)*U.astype(float64))*dx[0]*dx[1]/L[0]/L[1]/2)
        if rank == 0:
            print params.tstep, kk

if __name__ == "__main__":
    config.update(
        {
            'nu': 1.0e-08,
            'dt': 0.001,
            'T': 1.0,
            'U1':-0.5,
            'U2':0.5,
            'l0': 0.001,    # Smoothing parameter
            'A': 0.01,      # Amplitude of perturbation
            'Ri': 0.167,    # Richardson number
            'Pr': 12.0,     # Prantl number
            'delta': 0.05,   # Width of perturbations
            'bb': 0.8,
            'k0': 2,
            'rho1': 1.0,
            'rho2': 3.0,
        }, 'doublyperiodic'
    )
    config.doublyperiodic.add_argument("--plot_result", type=int, default=10)
    config.doublyperiodic.add_argument("--compute_energy", type=int, default=2)
    solver = get_solver(update, mesh='doublyperiodic')
    solver.hdf5file.components["curl"] = solver.curl
    
    initialize(**vars(solver))
    solver.solve()
