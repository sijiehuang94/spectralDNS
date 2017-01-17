import numpy as np
from .SFTc import CDNmat_matvec, BDNmat_matvec, CDDmat_matvec, SBBmat_matvec, \
    SBBmat_matvec3D, Biharmonic_matvec, Biharmonic_matvec3D, Tridiagonal_matvec, \
    Tridiagonal_matvec3D, Pentadiagonal_matvec, Pentadiagonal_matvec3D, \
    CBD_matvec3D, CBD_matvec, CDB_matvec3D, ADDmat_matvec, Helmholtz_matvec3D, \
    Helmholtz_matvec, BBD_matvec3D, Tridiagonal_matvec

from .shentransform import ChebyshevTransform, ShenDirichletBasis, ShenNeumannBasis, \
    ShenBiharmonicBasis

from . import points_and_weights
import numpy.polynomial.chebyshev as cheb
from scipy.sparse import diags
from collections import OrderedDict
import six
from copy import deepcopy

pi, zeros, ones, array = np.pi, np.zeros, np.ones, np.array
float, complex = np.float64, np.complex128

class SparseMatrix(dict):
    """Base class for sparse matrices

    The data is stored as a dictionary, where keys and values are,
    respectively, the offsets and values of the diagonal.

    A tridiagonal matrix of shape N x N could be created as

    >>> d = {-1: 1,
              0: -2,
              1: 1}

    >>> SparseMatrix(d, (N, N))

    In case of variable values, store the entire diagonal
    For an N x N matrix use:

    >>> d = {-1: np.ones(N-1),
              0: -2*np.ones(N),
              1: np.ones(N-1)}

    >>> SparseMatrix(d, (N, N))

    """

    def __init__(self, d, shape):
        dict.__init__(self, d)
        self.shape = shape
        self._diags = None

    #@profile
    def matvec(self, v, c, format='dia'):
        N, M = self.shape
        c.fill(0)
        if len(v.shape) > 1:
            if format == 'python':
                for key, val in six.iteritems(self):
                    if key < 0:
                        for i in range(v.shape[1]):
                            for j in range(v.shape[2]):
                                c[-key:min(N, M-key), i, j] += val*v[:min(M, N+key), i, j]
                    else:
                        for i in range(v.shape[1]):
                            for j in range(v.shape[2]):
                                c[:min(N, M-key), i, j] += val*v[key:min(M, N+key), i, j]

            else:
                assert format in ('csr', 'dia', 'csc')
                diags = self.diags(format=format)
                for i in range(v.shape[1]):
                    for j in range(v.shape[2]):
                        c[:N, i, j] = diags.dot(v[:M, i, j])

        else:
            if format == 'python':
                for key, val in six.iteritems(self):
                    if key < 0:
                        c[-key:min(N, M-key)] += val*v[:min(M, N+key)]
                    else:
                        c[:min(N, M-key)] += val*v[key:min(M, N+key)]

            else:
                assert format in ('csr', 'dia', 'csc')
                diags = self.diags(format=format)
                c[:N] = diags.dot(v[:M])

        return c

    def diags(self, format='dia'):
        """Return a regular sparse matrix of specified format

        args:
            - format  ('dia', 'csr', 'csc')

        """
        if self._diags is None:
            self._diags = diags(list(self.values()), list(self.keys()),
                                shape=self.shape, format=format)

        if self._diags.format != format:
            self._diags = diags(list(self.values()), list(self.keys()),
                                shape=self.shape, format=format)

        return self._diags

    def __imul__(self, alfa):
        """self *= alfa"""
        assert isinstance(alfa, (np.float, np.int))
        for key, val in six.iteritems(self):
            # Check if symmetric
            if key < 0 and (-key) in self:
                if id(self[key]) == id(self[-key]):
                    continue
            val *= alfa
        return self

    def __mul__(self, alfa):
        """Return copy self*alfa"""
        f = SparseMatrix(deepcopy(dict(self)), self.shape)
        assert isinstance(alfa, (np.float, np.int))
        for key, val in six.iteritems(f):
            # Check if symmetric
            if key < 0 and (-key) in f:
                if id(f[key]) == id(f[-key]):
                    continue
            val *= alfa
        return f

    def __rmul__(self, alfa):
        return self.__mul__(alfa)

    def __div__(self, alfa):
        """Return copy self/alfa"""
        f = SparseMatrix(deepcopy(dict(self)), self.shape)
        assert isinstance(alfa, (np.float, np.int))
        for key, val in six.iteritems(f):
            # Check if symmetric
            if key < 0 and (-key) in f:
                if id(f[key]) == id(f[-key]):
                    continue
            val /= alfa
        return f

    def __add__(self, d):
        """Return copy of self+d"""
        f = SparseMatrix(deepcopy(dict(self)), self.shape)
        if isinstance(d, dict):
            assert d.shape == self.shape
            for key, val in six.iteritems(d):
                if key in f:
                    # Check if symmetric and make copy if necessary
                    if (-key) in f:
                        if id(f[key]) == id(f[-key]):
                            f[-key] = deepcopy(f[key])
                    f[key] += val
                else:
                    f[key] = val

        elif isinstance(d, (np.float, np.int)):
            for key, val in six.iteritems(f):
                val += d
        return f

    def __iadd__(self, d):
        """self += d"""
        if isinstance(d, dict):
            assert d.shape == self.shape
            for key, val in six.iteritems(d):
                if key in self:
                    # Check if symmetric and make copy if necessary
                    if (-key) in self:
                        if id(self[key]) == id(self[-key]):
                            self[-key] = deepcopy(self[key])
                    self[key] += val
                else:
                    self[key] = val

        elif isinstance(d, (np.float, np.int)):
            for key, val in six.iteritems(self):
                val += d
        return self


class ShenMatrix(SparseMatrix):
    """Base class for Shen matrices

    args:
        d                            Dictionary, where keys are the diagonal
                                         offsets and values the diagonals
        N      integer               Length of main diagonal
        trial  (basis, derivative)   tuple, where basis is an instance of
                                     one of
                                         - ChebyshevTransform
                                         - ShenDirichletBasis
                                         - ShenBiharmonicBasis
                                         - ShenNeumannBasis
                                     derivative is an integer, and represents
                                     the number of times the trial function
                                     should be differentiated
        test   basis                 One of the above basis functions
        scale  float                 Scale matrix with this constant


    Shen matrices are assumed to be sparse diagonal. The matrices are
    scalar products of trial and test functions from one of four function
    spaces

    Chebyshev basis and space of first kind

        T_k,
        span(T_k) for k = 0, 1, ..., N

    For homogeneous Dirichlet boundary conditions:

        phi_k = T_k - T_{k+2},
        span(phi_k) for k = 0, 1, ..., N-2

    For homogeneous Neumann boundary conditions:

        phi_k = T_k - (k/(k+2))**2T_{k+2},
        span(phi_k) for k = 1, 2, ..., N-2

    For Biharmonic basis with both homogeneous Dirichlet
    and Neumann:

        psi_k = T_k - 2(k+2)/(k+3)*T_{k+2} + (k+1)/(k+3)*T_{k+4},
        span(psi_k) for k = 0, 1, ..., N-4

    The scalar product is computed as a weighted inner product with
    w=1/sqrt(1-x**2) the weights.

    Mass matrix for Dirichlet basis:

        (phi_k, phi_j)_w = \int_{-1}^{1} phi_k phi_j w dx

    Stiffness matrix for Dirichlet basis:

        (phi_k'', phi_j)_w = \int_{-1}^{1} phi_k'' phi_j w dx

    etc.

    The matrix can be automatically created using, e.g., for the mass
    matrix of the Dirichlet space

      M = ShenMatrix({}, 16, (ShenDirichletBasis(), 0), ShenDirichletBasis())

    where the first (ShenDirichletBasis, 0) represents the trial function and
    the second the test function. The stiffness matrix can be obtained as

      A = ShenMatrix({}, 16, (ShenDirichletBasis(), 2), ShenDirichletBasis())

    where (ShenDirichletBasis, 2) signals that we use the second derivative
    of this trial function.

    The automatically created matrices may be overloaded with more exactly
    computed diagonals.

    Note that matrices with the Neumann basis are stored using index space
    k = 0, 1, ..., N-2, i.e., including the zero index. This is used for
    simplicity, and needs to be accounted for by users. For example, to
    solve the Poisson equation:

        from spectralDNS.shen.shentransform import ShenNeumannBasis
        import numpy as np
        from sympy import Symbol, sin, pi
        M = 32
        SN = ShenNeumannBasis('GC')
        x = Symbol("x")
        u = (1-x**2)*sin(np.pi*x)
        f = -u.diff(x, 2)
        points, weights = SN.points_and_weights(M, SN.quad)
        uj = np.array([u.subs(x, h) for h in points], dtype=np.float)
        fj = np.array([f.subs(x, h) for h in points], dtype=np.float)
        A = ShenMatrix({}, M, (SN, 2), SN, scale=-1)
        s = slice(1, M-2)
        # Subtract mean
        fj -= np.dot(fj, weights)/weights.sum()
        uj -= np.dot(uj, weights)/weights.sum()
        f_hat = np.zeros(M)
        f_hat = SN.scalar_product(fj, f_hat)
        u_hat = np.zeros(M)
        u_hat[s] = np.linalg.solve(A.diags().toarray()[s, s], f_hat[s])
        u0 = np.zeros(M)
        u0 = SN.ifst(u_hat, u0)
        assert np.allclose(u0, uj)


    """
    def __init__(self, d, N,  trial, test, scale=1.0):
        self.trialfunction, self.derivative = trial
        self.testfunction = test
        self.N = N
        self.scale = scale
        shape = self.get_shape()
        if d == {}:
            D = self.get_dense_matrix()[:shape[0], :shape[1]]
            d = extract_diagonal_matrix(D)
        SparseMatrix.__init__(self, d, shape)
        if not round(scale-1.0, 8) == 0:
            self *= scale

    def get_shape(self):
        return (self.testfunction.get_shape(self.N),
                self.trialfunction.get_shape(self.N))

    def get_ck(self, N, quad):
        ck = ones(N, int)
        ck[0] = 2
        if quad == "GL": ck[-1] = 2
        return ck

    def get_dense_matrix(self):
        """Return dense matrix automatically computed from basis"""
        N = self.N
        x, w = points_and_weights(N, self.trialfunction.quad)
        V = self.testfunction.vandermonde(x, N)
        test = self.testfunction.get_vandermonde_basis(V)
        trial = self.trialfunction.get_vandermonde_basis_derivative(V, self.derivative)
        return np.dot(w*test.T, trial)

    def test(self):
        """Test for matrix.

        Test that automatically created matrix is the same as the one created

        """
        N, M = self.shape
        D = self.get_dense_matrix()[:N, :M]
        Dsp = extract_diagonal_matrix(D)
        Dsp *= self.scale
        for key, val in six.iteritems(self):
            assert np.allclose(val, Dsp[key])

def extract_diagonal_matrix(M, tol=1e-8):
    """Return matrix with essentially zero diagonals nulled out
    """
    du = []
    dl = []
    d = {}
    for i in range(M.shape[1]):
        u = M.diagonal(i).copy()
        if abs(u).max() > tol:
            d[i] = u

    for i in range(1, M.shape[0]):
        l = M.diagonal(-i).copy()
        if abs(l).max() > tol:
            d[-i] = l

    return SparseMatrix(d, M.shape)


class BDDmat(ShenMatrix):
    """Matrix for inner product (u, phi)_w = BDDmat * u_hat

    where u_hat is a vector of coefficients for a Shen Dirichlet basis
    and phi is a Shen Dirichlet basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        ck = self.get_ck(N, quad)
        data = {-2: np.array([-pi/2.]),
                 0: pi/2*(ck[:-2]+ck[2:]),
                 2: np.array([-pi/2])}
        trial = ShenDirichletBasis(quad=quad)
        ShenMatrix.__init__(self, data, N, (trial, 0), trial)

    #@profile
    def matvec(self, v, c, format='cython'):
        N, M = self.shape
        c.fill(0)
        if len(v.shape) > 1:
            ld = self[-2]*np.ones(M-2)
            if format == 'cython':
                Tridiagonal_matvec3D(v, c, ld, self[0], ld)

            elif format == 'self':
                c[:(N-2)] = self[2]*v[2:N]
                c[:N]    += self[0].repeat(array(v.shape[1:]).prod()).reshape(v[:N].shape)*v[:N]
                c[2:N]   += self[-2]*v[:(N-2)]

            else:
                c = ShenMatrix.matvec(self, v, c, format=format)

        else:
            if format == 'cython':
                ld = self[-2]*np.ones(M-2)
                Tridiagonal_matvec(v, c, ld, self[0], ld)

            elif format == 'self':
                c[:(N-2)] = self[2]*v[2:M]
                c[:N]    += self[0]*v[:M]
                c[2:N]   += self[-2]*v[:(M-2)]

            else:
                c = ShenMatrix.matvec(self, v, c, format=format)

        return c


## Mass matrices
class BNDmat(ShenMatrix):
    """Matrix for inner product (u, phi)_w = BNDmat * u_hat

    where u_hat is a vector of coefficients for a Shen Dirichlet basis
    and phi is a Shen Neumann basis.
    """

    def __init__(self, K, quad='GC'):
        N = K.shape[0]
        ck = self.get_ck(N, quad)
        k = K[:N-2].astype(float)
        d = {-2: -pi/2,
              0: pi/2.*(ck[:-2]+ck[2:]*(k/(k+2))**2),
              2: -pi/2*(k[:N-4]/(k[:N-4]+2))**2}
        trial = ShenDirichletBasis(quad=quad)
        test  = ShenNeumannBasis(quad=quad)
        ShenMatrix.__init__(self, d, N, (trial, 0), test)

    def matvec(self, v, c, format='csr'):
        c = ShenMatrix.matvec(self, v, c, format=format)
        c[0] = 0
        return c


class BDNmat(ShenMatrix):
    """Matrix for inner product (p, phi)_w = BDNmat * p_hat

    where p_hat is a vector of coefficients for a Shen Neumann basis
    and phi is a Shen Dirichlet basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        ck = self.get_ck(N, quad)
        k = K[:N-2].astype(float)
        d = {-2: -pi/2*(k[:N-4]/(k[:N-4]+2))**2,
              0:  pi/2.*(ck[:-2]+ck[2:]*(k/(k+2))**2),
              2: -pi/2}
        trial = ShenNeumannBasis(quad=quad)
        test  = ShenDirichletBasis(quad=quad)
        ShenMatrix.__init__(self, d, N, (trial, 0), test)


class BTTmat(ShenMatrix):
    """Matrix for inner product (p, T)_w = BTTmat * p_hat

    where p_hat is a vector of coefficients for a Chebyshev basis
    and T is a Chebyshev basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        ck = self.get_ck(N, quad)
        trial = ChebyshevTransform(quad)
        ShenMatrix.__init__(self, {0: pi/2*ck}, N, (trial, 0), trial)

    def matvec(self, v, c, format='self'):
        N = self.shape[0]
        c.fill(0)
        if len(v.shape) > 1:
            if format == 'self':
                c[:] = self[0].repeat(array(v.shape[1:]).prod()).reshape(v[:].shape)*v
            else:
                c = ShenMatrix.matvec(self, v, c, format=format)

        else:
            if format == 'self':
                c[:] = self[0]*v
            else:
                c = ShenMatrix.matvec(self, v, c, format=format)

        return c


class BNNmat(ShenMatrix):
    """Matrix for inner product (p, phi_N)_w = BNNmat * p_hat

    where p_hat is a vector of coefficients for a Shen Neumann basis
    and phi_N is a Shen Neumann basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        ck = self.get_ck(N, quad)
        k = K[:-2].astype(float)
        d = {-2: -pi/2*((k[2:]-2)/(k[2:]))**2,
              0: pi/2*(ck[:-2]+ck[2:]*(k[:]/(k[:]+2))**4),
              2: -pi/2*((k[2:]-2)/(k[2:]))**2}
        trial = ShenNeumannBasis(quad)
        ShenMatrix.__init__(self, d, N, (trial, 0), trial)

    def matvec(self, v, c, format='csr'):
        c = ShenMatrix.matvec(self, v, c, format=format)
        c[0] = 0
        return c


class BDTmat(ShenMatrix):
    """Matrix for inner product (u, phi)_w = BDTmat * u_hat

    where u_hat is a vector of coefficients for a Chebyshev basis
    and phi is a Shen Dirichlet basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        ck = self.get_ck(N, quad)
        d = {0: pi/2*ck[:N-2],
             2: -pi/2*ck[2:]}
        trial = ChebyshevTransform(quad)
        test = ShenDirichletBasis(quad)
        ShenMatrix.__init__(self, d, N, (trial, 0), test)


class BTDmat(ShenMatrix):
    """Matrix for inner product (u, T)_w = BTDmat * u_hat

    where u_hat is a vector of coefficients for a Shen Dirichlet basis
    and T is a Chebyshev basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        ck = self.get_ck(N, quad)
        d = {-2: -pi/2*ck[2:],
              0: pi/2*ck[:N-2]}
        test  = ChebyshevTransform(quad)
        trial = ShenDirichletBasis(quad)
        ShenMatrix.__init__(self, d, N, (trial, 0), test)


class BTNmat(ShenMatrix):
    """Matrix for inner product (u, T)_w = BTNmat * u_hat

    where u_hat is a vector of coefficients for a Shen Neumann basis
    and T is a Chebyshev basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        ck = self.get_ck(N, quad)
        d = {-2: -pi/2*ck[2:]*((K[2:]-2)/K[2:])**2,
              0: pi/2*ck[:-2]}
        trial = ShenNeumannBasis(quad)
        test = ChebyshevTransform(quad)
        ShenMatrix.__init__(self, d, N, (trial, 0), test)


class BBBmat(ShenMatrix):

    def __init__(self, K, quad='GC'):
        N = K.shape[0]
        ck = self.get_ck(N, quad)
        k = K[:N-4].astype(float)

        d = {4: (k[:-4]+1)/(k[:-4]+3)*pi/2,
             2: -((k[:-2]+2)/(k[:-2]+3) + (k[:-2]+4)*(k[:-2]+1)/((k[:-2]+5)*(k[:-2]+3)))*pi,
             0: (ck[:N-4] + 4*((k+2)/(k+3))**2 + ck[4:]*((k+1)/(k+3))**2)*pi/2.}
        d[-2] = d[2]
        d[-4] = d[4]
        trial = ShenBiharmonicBasis(quad)
        ShenMatrix.__init__(self, d, N, (trial, 0), trial)

    def matvec(self, v, c, format='cython'):
        c.fill(0)
        N = self.shape[0]
        if len(v.shape) > 1:
            if format == 'self':
                vv = v[:-4]
                c[:N] = self[0].repeat(array(v.shape[1:]).prod()).reshape(vv.shape) * vv[:]
                c[:N-2] += self[2].repeat(array(v.shape[1:]).prod()).reshape(vv[2:].shape) * vv[2:]
                c[:N-4] += self[4].repeat(array(v.shape[1:]).prod()).reshape(vv[4:].shape) * vv[4:]
                c[2:N]  += self[-2].repeat(array(v.shape[1:]).prod()).reshape(vv[:-2].shape) * vv[:-2]
                c[4:N]  += self[-4].repeat(array(v.shape[1:]).prod()).reshape(vv[:-4].shape) * vv[:-4]

            elif format == 'cython':
                Pentadiagonal_matvec3D(v, c, self[-4], self[-2], self[0], self[2], self[4])

            else:
                c = ShenMatrix.matvec(self, v, c, format=format)

        else:
            if format == 'self':
                vv = v[:-4]
                c[:N] = self[0] * vv[:]
                c[:N-2] += self[2] * vv[2:]
                c[:N-4] += self[4] * vv[4:]
                c[2:N]  += self[-2] * vv[:-2]
                c[4:N]  += self[-4] * vv[:-4]

            elif format == 'cython':
                Pentadiagonal_matvec(v, c, self[-4], self[-2], self[0], self[2], self[4])

            else:
                c = ShenMatrix.matvec(self, v, c, format=format)

        return c


#import decimal
#class BBBmat(BaseMatrix):

    #def __init__(self, K, quad='GC'):
        #BaseMatrix.__init__(self)
        #N = K.shape[0]-4
        #self.shape = (N, N)
        #ck = ones(N)
        #ckp = ones(N)
        #ck[0] = 2
        #if quad == "GL": ckp[-1] = 2
        #k = K[:N].astype(float)

        #self.dd = (ck + 4*((k+2)/(k+3))**2 + ckp*((k+1)/(k+3))**2)*pi/2.
        #self.ud = -((k[:-2]+2)/(k[:-2]+3) + (k[:-2]+4)*(k[:-2]+1)/((k[:-2]+5)*(k[:-2]+3)))*pi
        #self.uud = (k[:-4]+1)/(k[:-4]+3)*pi/2
        ##kd = array(map(decimal.Decimal, K[:N]))
        ##ckd = array(map(decimal.Decimal, [1,]*N))
        ##ckdp = array(map(decimal.Decimal, [1,]*N))
        ##ckd[0] = decimal.Decimal(2)
        ##if quad == "GL": ckdp[-1] = decimal.Decimal(2)
        ##one = decimal.Decimal(1)
        ##two = decimal.Decimal(2)
        ##three = decimal.Decimal(3)
        ##four = decimal.Decimal(4)
        ##five = decimal.Decimal(5)
        ##PI = decimal.Decimal("3.1415926535897932384626433832795028841971693993751058209749445923078164062862089")

        ###dd = (ckd + four*((kd+two)/(kd+three))**two + ckdp*((kd+one)/(kd+three))**two)*PI/two
        ##dd = (ckd + four*((kd+two)*(kd+two)/(kd+three)/(kd+three)) + ckdp*((kd+one)*(kd+one)/(kd+three)/(kd+three)))*PI/two
        ##ud = -((kd[:-2]+two)/(kd[:-2]+three) + (kd[:-2]+four)*(kd[:-2]+one)/((kd[:-2]+five)*(kd[:-2]+three)))*PI
        ##uud = (kd[:-4]+one)/(kd[:-4]+three)*PI/two

        ###self.dd = dd.astype(float)
        ###self.ud = ud.astype(float)
        ###self.uud = uud.astype(float)
        ##self.dd = dd
        ##self.ud = ud
        ##self.uud = uud

        #self.ld = self.ud
        #self.lld = self.uud

    #def matvec(self, v):
        #c = self.get_return_array(v)
        #N = self.shape[0]
        #if len(v.shape) > 1:
            ##vv = v[:-4]
            ##c[:N] = self.dd.repeat(array(v.shape[1:]).prod()).reshape(vv.shape) * vv[:]
            ##c[:N-2] += self.ud.repeat(array(v.shape[1:]).prod()).reshape(vv[2:].shape) * vv[2:]
            ##c[:N-4] += self.uud.repeat(array(v.shape[1:]).prod()).reshape(vv[4:].shape) * vv[4:]
            ##c[2:N]  += self.ld.repeat(array(v.shape[1:]).prod()).reshape(vv[:-2].shape) * vv[:-2]
            ##c[4:N]  += self.lld.repeat(array(v.shape[1:]).prod()).reshape(vv[:-4].shape) * vv[:-4]
            #Pentadiagonal_matvec3D(v, c, self.lld, self.ld, self.dd, self.ud, self.uud)

        #else:
            ##vv = v[:-4]
            ##c[:N] = self.dd * vv[:]
            ##c[:N-2] += self.ud * vv[2:]
            ##c[:N-4] += self.uud * vv[4:]
            ##c[2:N]  += self.ld * vv[:-2]
            ##c[4:N]  += self.lld * vv[:-4]
            #Pentadiagonal_matvec(v, c, self.lld, self.ld, self.dd, self.ud, self.uud)

        #return c

    #def diags(self):
        #return diags([self.lld, self.ld, self.dd, self.ud, self.uud], range(-4, 6, 2), shape=self.shape)

class BBDmat(ShenMatrix):

    def __init__(self, K, quad='GC'):
        N = K.shape[0]
        ck = self.get_ck(N, quad)
        k = K[:N-4].astype(float)
        a = 2*(k+2)/(k+3)
        b = (k[:N-4]+1)/(k[:N-4]+3)
        d = {-2: -pi/2,
              0: (ck[:N-4] + a)*pi/2,
              2: -(a+b*ck[4:])*pi/2,
              4: b[:-2]*pi/2}
        trial = ShenDirichletBasis(quad)
        test = ShenBiharmonicBasis(quad)
        ShenMatrix.__init__(self, d, N, (trial, 0), test)

    def matvec(self, v, c, format='cython'):
        c.fill(0)
        N = self.shape[0]
        if len(v.shape) > 1:
            if format == 'self':
                vv = v[:-2]
                c[:N] = self[0].repeat(array(v.shape[1:]).prod()).reshape(vv[:-2].shape) * vv[:-2]
                c[:N] += self[2].repeat(array(v.shape[1:]).prod()).reshape(vv[2:].shape) * vv[2:]
                c[:N-2] += self[4].repeat(array(v.shape[1:]).prod()).reshape(vv[4:].shape) * vv[4:]
                c[2:N]  += self[-2] * vv[:-4]

            elif format == 'cython':
                BBD_matvec3D(v, c, self[-2], self[0], self[2], self[4])

            else:
                c = ShenMatrix.matvec(self, v, c, format=format)

        else:
            if format == 'self':
                vv = v[:-2]
                c[:N] = self[0] * vv[:-2]
                c[:N] += self[2] * vv[2:]
                c[:N-2] += self[4] * vv[4:]
                c[2:N]  += self[-2] * vv[:-4]
            else:
                if format == 'cython': format = 'csr'
                c = ShenMatrix.matvec(self, v, c, format=format)

        return c

# Derivative matrices
class CDNmat(ShenMatrix):
    """Matrix for inner product (p', phi)_w = CDNmat * p_hat

    where p_hat is a vector of coefficients for a Shen Neumann basis
    and phi is a Shen Dirichlet basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        k = K[:N-2].astype(float)
        d = {-1: -((k[1:]-1)/(k[1:]+1))**2*(k[1:]+1)*pi,
              1: (k[:-1]+1)*pi}
        trial = ShenNeumannBasis()
        test = ShenDirichletBasis()
        ShenMatrix.__init__(self, d, N, (trial, 1), test)

    def matvec(self, v, c, format='cython'):
        N = self.shape[0]
        if len(v.shape) > 1:
            if format == 'cython':
                CDNmat_matvec(self[1], self[-1][1:], v, c)
            else:
                c = ShenMatrix.matvec(self, v, c, format=format)
        else:
            if format == 'cython': format = 'csr'
            c = ShenMatrix.matvec(self, v, c, format=format)

        return c


class CDDmat(ShenMatrix):
    """Matrix for inner product (u', phi) = (phi', phi) u_hat =  CDDmat * u_hat

    where u_hat is a vector of coefficients for a Shen Dirichlet basis
    and phi is a Shen Dirichlet basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        d = {-1: -(K[1:N-2]+1)*pi,
              1: (K[:(N-3)]+1)*pi}
        trial = ShenDirichletBasis()
        ShenMatrix.__init__(self, d, N, (trial, 1), trial)

    def matvec(self, v, c, format='cython'):
        N = self.shape[0]
        c.fill(0)
        if len(v.shape) > 1:
            if format == 'self':
                c[:N-1] = self.ud.repeat(array(v.shape[1:]).prod()).reshape(v[1:N].shape)*v[1:N]
                c[1:N] += self.ld.repeat(array(v.shape[1:]).prod()).reshape(v[:(N-1)].shape)*v[:(N-1)]
            elif format == 'cython':
                CDDmat_matvec(self[1], self[-1], v, c)
            else:
                c = ShenMatrix.matvec(self, v, c, format=format)
        else:
            if format == 'self':
                c[:N-1] = self.ud*v[1:N]
                c[1:N] += self.ld*v[:(N-1)]
            else:
                if format == 'cython': format='csr'
                c = ShenMatrix.matvec(self, v, c, format=format)

        return c


class CNDmat(ShenMatrix):
    """Matrix for inner product (u', phi_N) = (phi', phi_N) u_hat =  CNDmat * u_hat

    where u_hat is a vector of coefficients for a Shen Dirichlet basis
    and phi_N is a Shen Neumann basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        k = K[:N-2].astype(float)
        d = {-1: -(k[1:]+1)*pi,
              1: -(2-k[:-1]**2/(k[:-1]+2)**2*(k[:-1]+3))*pi}
        for i in range(3, N-1, 2):
            d[i] = -(1-k[:-i]**2/(k[:-i]+2)**2)*2*pi
        trial = ShenDirichletBasis()
        test = ShenNeumannBasis()
        ShenMatrix.__init__(self, d, N, (trial, 1), test)

    def matvec(self, v, c, format='csr'):
        c = ShenMatrix.matvec(self, v, c, format=format)
        c[0] = 0
        return c


class CTDmat(ShenMatrix):
    """Matrix for inner product (u', T) = (phi', T) u_hat =  CTDmat * u_hat

    where u_hat is a vector of coefficients for a Shen Dirichlet basis
    and T is a Chebyshev basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        d = {-1: -(K[1:N-1]+1)*pi,
              1: -2*pi}
        for i in range(3, N-2, 2):
            d[i] = -2*pi
        trial = ShenDirichletBasis()
        test = ChebyshevTransform()
        ShenMatrix.__init__(self, d, N, (trial, 1), test)


class CDTmat(ShenMatrix):
    """Matrix for inner product (p', phi) = (T', phi) p_hat = CDTmat * p_hat

    where p_hat is a vector of coefficients for a Chebyshev basis
    and phi is a Shen Dirichlet basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        d = {1: pi*(K[:N-2]+1)}
        trial = ChebyshevTransform()
        test = ShenDirichletBasis()
        ShenMatrix.__init__(self, d, N, (trial, 1), test)


class CBDmat(ShenMatrix):
    """Matrix for inner product (u', psi) = (phi', psi) u_hat =  CBDmat * u_hat

    where u_hat is a vector of coefficients for a Shen Dirichlet basis
    and psi is a Shen Biharmonic basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        d = {-1: -(K[1:N-4]+1)*pi,
              1: 2*(K[:N-4]+1)*pi,
              3: -(K[:N-5]+1)*pi}
        trial = ShenDirichletBasis()
        test = ShenBiharmonicBasis()
        ShenMatrix.__init__(self, d, N, (trial, 1), test)

    def matvec(self, v, c, format='cython'):
        N, M = self.shape
        c.fill(0)
        if len(v.shape) > 1:
            if format == 'self':
                c[1:N] = self[-1].repeat(array(v.shape[1:]).prod()).reshape(v[:M-3].shape)*v[:M-3]
                c[:N] += self[1].repeat(array(v.shape[1:]).prod()).reshape(v[1:M-1].shape)*v[1:M-1]
                c[:N-1]+= self[3].repeat(array(v.shape[1:]).prod()).reshape(v[3:M].shape)*v[3:M]
            elif format == 'cython':
                CBD_matvec3D(v, c, self[-1], self[1], self[3])
            else:
                c = ShenMatrix.matvec(self, v, c, format=format)
        else:
            if format == 'self':
                c[1:N] = self[-1] * v[:M-3]
                c[:N] += self[1] * v[1:M-1]
                c[:N-1] += self[3] * v[3:M]
            elif format == 'cython':
                CBD_matvec(v, c, self[-1], self[1], self[3])
            else:
                c = ShenMatrix.matvec(self, v, c, format=format)
        return c


class CDBmat(ShenMatrix):
    """Matrix for inner product (u', psi) = (phi', psi) u_hat =  CDBmat * u_hat

    where u_hat is a vector of coefficients for a Shen Biharmonic basis
    and psi is a Shen Dirichlet basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        d = {-3: (K[3:-2]-2)*(K[3:-2]+1)/K[3:-2]*pi,
             -1: -2*(K[1:-3]+1)**2/(K[1:-3]+2)*pi,
              1: (K[:-5]+1)*pi}
        trial = ShenBiharmonicBasis()
        test = ShenDirichletBasis()
        ShenMatrix.__init__(self, d, N, (trial, 1), test)

    def matvec(self, v, c, format='cython'):
        N, M = self.shape
        c.fill(0)
        if len(v.shape) > 1:
            if format == 'self':
                c[3:N] = self[-3].repeat(array(v.shape[1:]).prod()).reshape(v[:M-1].shape) * v[:M-1]
                c[1:N-1] += self[-1].repeat(array(v.shape[1:]).prod()).reshape(v[:M].shape) * v[:M]
                c[:N-3] += self[1].repeat(array(v.shape[1:]).prod()).reshape(v[1:M].shape) * v[1:M]
            elif format == 'cython':
                CDB_matvec3D(v, c, self[-3], self[-1], self[1])
            else:
                c = ShenMatrix.matvec(self, v, c, format=format)

        else:
            if format == 'self':
                c[3:N] = self[-3] * v[:M-1]
                c[1:N-1] += self[-1] * v[:M]
                c[:N-3] += self[1] * v[1:M]
            else:
                if format == 'cython': format = 'csr'
                c = ShenMatrix.matvec(self, v, c, format=format)

        return c


class ABBmat(ShenMatrix):
    """Matrix for inner product (u'', phi) = (phi'', phi) u_hat =  ABBmat * u_hat

    where u_hat is a vector of coefficients for a Shen Biharmonic basis
    and phi is a Shen Biharmonic basis.
    """

    def __init__(self, K, quad='GC'):
        N = K.shape[0]
        ki = K[:N-4]
        k = K[:N-4].astype(float)
        d = {-2: 2*(ki[2:]-1)*(ki[2:]+2)*pi,
              0: -4*((ki+1)*(ki+2)**2)/(k+3)*pi,
              2: 2*(ki[:-2]+1)*(ki[:-2]+2)*pi}
        trial = ShenBiharmonicBasis()
        ShenMatrix.__init__(self, d, N, (trial, 2), trial)

    def matvec(self, v, c, format='cython'):
        N = self.shape[0]
        c.fill(0)
        if len(v.shape) > 1:
            if format == 'self':
                c[:N] = self[0].repeat(array(v.shape[1:]).prod()).reshape(v[:N].shape) * v[:N]
                c[:N-2] += self[2].repeat(array(v.shape[1:]).prod()).reshape(v[2:N].shape) * v[2:N]
                c[2:N] += self[-2].repeat(array(v.shape[1:]).prod()).reshape(v[:N-2].shape) * v[:N-2]
            elif format == 'cython':
                Tridiagonal_matvec3D(v, c, self[-2], self[0], self[2])
            else:
                c = ShenMatrix.matvec(self, v, c, format=format)

        else:
            if format == 'self':
                c[:N] = self[0] * v[:N]
                c[:N-2] += self[2] * v[2:N]
                c[2:N] += self[-2] * v[:N-2]
            elif format == 'cython':
                Tridiagonal_matvec(v, c, self[-2], self[0], self[2])
            else:
                c = ShenMatrix.matvec(self, v, c, format=format)

        return c


class ADDmat(ShenMatrix):
    """Matrix for inner product -(u'', phi) = -(phi'', phi) u_hat = ADDmat * u_hat

    where u_hat is a vector of coefficients for a Shen Dirichlet basis
    and phi is a Shen Dirichlet basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        d = {0: -2*np.pi*(K[:N-2]+1)*(K[:N-2]+2)}
        for i in range(2, N-2, 2):
            d[i] = -4*np.pi*(K[:-(i+2)]+1)
        trial = ShenDirichletBasis()
        ShenMatrix.__init__(self, d, N, (trial, 2), trial, -1.0)

    def matvec(self, v, c, format='cython'):
        N = self.shape[0]
        c = np.zeros(v.shape, dtype=v.dtype)
        if len(v.shape) > 1:
            if format == 'cython': format = 'csr'
            c = ShenMatrix.matvec(self, v, c, format=format)

        else:
            if format == 'cython':
                ADDmat_matvec(v, c, self[0])
            else:
                c = ShenMatrix.matvec(self, v, c, format=format)

        return c


class ANNmat(ShenMatrix):
    """Matrix for inner product -(u'', phi_N) = -(phi_N'', phi_N) p_hat = ANNmat * p_hat

    where u_hat is a vector of coefficients for a Shen Neumann basis
    and phi is a Shen Neumann basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        k = K[:-2].astype(float)
        d = {0: -2*pi*k**2*(k+1)/(k+2)}
        for i in range(2, N-2, 2):
            d[i] = -4*np.pi*(k[:-i]+i)**2*(k[:-i]+1)/(k[:-i]+2)**2
        trial = ShenNeumannBasis()
        ShenMatrix.__init__(self, d, N, (trial, 2), trial, -1.0)

    def matvec(self, v, c, format='csr'):
        c = ShenMatrix.matvec(self, v, c, format=format)
        c[0] = 0
        return c


class ATTmat(ShenMatrix):
    """Matrix for inner product -(u'', phi) = -(phi'', phi) p_hat = ATTmat * p_hat

    where p_hat is a vector of coefficients for a Chebyshev basis
    and phi is a Chebyshev basis.
    """

    def __init__(self, K, quad='GC'):
        assert len(K.shape) == 1
        N = K.shape[0]
        d = {}
        for j in range(2, N, 2):
            d[j] = K[j:]*(K[j:]**2-K[:-j]**2)*np.pi/2.
        trial = ChebyshevTransform()
        ShenMatrix.__init__(self, d, N, (trial, 2), trial, -1.0)


class SBBmat(ShenMatrix):
    """Matrix for inner product (u'''', phi) = (phi'''', phi) u_hat =  SBBmat * u_hat

    where u_hat is a vector of coefficients for a Shen Biharmonic basis
    and phi is a Shen Biharmonic basis.
    """

    def __init__(self, K, quad='GC'):
        N = K.shape[0]
        k = K[:N-4].astype(float)
        ki = K[:N-4]
        i = 8*(ki+1)**2*(ki+2)*(ki+4)
        d = {0: i * pi}
        for j in range(2, N-4, 2):
            i = 8*(ki[:-j]+1)*(ki[:-j]+2)*(ki[:-j]*(ki[:-j]+4)+3*(ki[j:]+2)**2)
            d[j] = np.array(i*pi/(k[j:]+3))
        trial = ShenBiharmonicBasis()
        ShenMatrix.__init__(self, d, N, (trial, 4), trial)

    def matvec(self, v, c, format='cython'):
        N = self.shape[0]
        c.fill(0)
        if len(v.shape) > 1:
            if format == 'cython':
                SBBmat_matvec3D(v, c, self[0])
            else:
                c = ShenMatrix.matvec(self, v, c, format=format)
        else:
            if format == 'cython':
                SBBmat_matvec(v, c, self[0])
            else:
                c = ShenMatrix.matvec(self, v, c, format=format)

        return c


class BiharmonicCoeff(object):

    def __init__(self, K, a0, alfa, beta, quad="GL"):
        self.quad = quad
        N = K.shape[0]
        self.shape = (N-4, N-4)
        self.S = SBBmat(K)
        self.B = BBBmat(K, self.quad)
        self.A = ABBmat(K)
        self.a0 = a0
        self.alfa = alfa
        self.beta = beta

    def matvec(self, v, c):
        N = self.shape[0]
        #c = np.zeros(v.shape, dtype=v.dtype)
        c.fill(0)
        if len(v.shape) > 1:
            Biharmonic_matvec3D(v, c, self.a0, self.alfa, self.beta, self.S[0], self.S[2],
                                self.S[4], self.A[-2], self.A[0], self.A[2],
                                self.B[-4], self.B[-2], self.B[0], self.B[2], self.B[4])
        else:
            Biharmonic_matvec(v, c, self.a0, self.alfa, self.beta, self.S[0], self.S[2],
                                self.S[4], self.A[-2], self.A[0], self.A[2],
                                self.B[-4], self.B[-2], self.B[0], self.B[2], self.B[4])
        return c


class HelmholtzCoeff(object):

    def __init__(self, K, alfa, beta, quad="GL"):
        """alfa*ADD + beta*BDD
        """
        self.quad = quad
        N = self.N = K.shape[0]-2
        self.shape = (N, N)
        self.B = BDDmat(K, self.quad)
        self.A = ADDmat(K)
        self.alfa = alfa
        self.beta = beta

    def matvec(self, v, c):
        N = self.shape[0]
        c.fill(0)
        if len(v.shape) > 1:
            Helmholtz_matvec3D(v, c, self.alfa, self.beta, self.A[0], self.A[2], self.B[0])
        else:
            Helmholtz_matvec(v, c, self.alfa, self.beta, self.A[0], self.A[2], self.B[0])
        return c

