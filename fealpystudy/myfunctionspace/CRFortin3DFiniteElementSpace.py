import numpy as np
from scipy.sparse import csr_matrix, spdiags, bmat

from fealpy.decorator import barycentric
from fealpy.quadrature import FEMeshIntegralAlg
from fealpy.functionspace.Function import Function




class CR_FortinDof():
    """
        Define the Forin element's dof
    """
    def __init__(self, mesh):
        self.mesh = mesh
        self.itype = mesh.itype
        self.ftype = mesh.ftype
        self.cell2dof = self.cell_to_dof()


    def cell_to_dof(self, index=np.s_[:]):
        mesh = self.mesh
        NE = mesh.number_of_edges()
        NF = mesh.number_of_faces()
        NC = mesh.number_of_cells()
        
        cell2dof = np.vstack((mesh.ds.cell_to_edge().T,
                              NE+mesh.ds.cell_to_face().T,
                                    NE+NF+np.arange(0,NC))).T 
        # cell2dof.shape = (NC,ldof), ldof = 11

        return cell2dof[index]

    def face_to_dof(self, index=np.s_[:]):
        mesh = self.mesh 
        NE = mesh.number_of_edges()
        NF = mesh.number_of_faces()
        face2dof = np.vstack((mesh.ds.face_to_edge().T,
                                    NE+np.arange(0,NF))).T
        # face2dof.shape = (NF, 4)
        '''
        face = mesh.entity('face')
        edge = mesh.entity('edge')
        face_to_edge = mesh.ds.face_to_edge()
        print(face[1,:],edge[4,:],face_to_edge[1,:])
        '''
        return face2dof[index]

    def edge_to_dof(self, index=np.s_[:]):
        mesh = self.mesh
        NE = mesh.number_of_edges()
        edge2dof = np.arange(0,NE)
        # edge2dof.shape = (NE, )

        return edge2dof

        
    def interpolation_points(self):
        mesh = self.mesh
        ipoints = np.vstack((mesh.entity_barycenter('edge'),
                                mesh.entity_barycenter('face'),
                                    mesh.entity_barycenter('cell')))
        # ipoints.shape = (gdof,3)
        return ipoints

    def Forininterpolation_points(self):
        mesh = self.mesh
        ipoints = np.vstack((mesh.entity_barycenter('edge'),
                                mesh.entity('node')))
        # ipoints.shape = (NE+NN, 3)
        return ipoints


    def number_of_global_dofs(self):
        return self.mesh.number_of_edges()+self.mesh.number_of_faces()+self.mesh.number_of_cells()

    def number_of_local_dofs(self, doftype='cell'):
        if doftype in {'cell'}:
            return 11
        elif doftype in {'face'}:
            return 4
        elif doftype in {'edge'}:
            return 1
        elif doftype in {'node'}:
            return 0


    def is_boundary_dof(self, threshold=None):
        if type(threshold) is np.ndarray:
            index = threshold
        else:
            index = self.mesh.ds.boundary_face_index()
            if callable(threshold):
                bc = self.mesh.entity_barycenter('face', index=index)
                flag = threshold(bc)
                index = index[flag]

        gdof = self.number_of_global_dofs()
        face2dof = self.face_to_dof()
        #print(face2dof.shape)
        isBdDof = np.zeros(gdof,dtype=np.bool)
        isBdDof[np.unique(face2dof[index,:].ravel())] = True

        return isBdDof

class CRFortin3DFiniteElementSpace():
    def __init__(self, mesh, q=None):
        self.mesh = mesh
        self.cellmeasure = mesh.entity_measure('cell')

        self.dof = CR_FortinDof(mesh)
        self.TD = mesh.top_dimension()
        self.GD = mesh.geo_dimension()

        self.itype = mesh.itype
        self.ftype = mesh.ftype

        q = 4
        self.integralalg = FEMeshIntegralAlg(
                self.mesh, q,
                cellmeasure=self.cellmeasure)
        self.integrator = self.integralalg.integrator

    def number_of_global_dofs(self):
        return self.mesh.number_of_edges()+self.mesh.number_of_faces()+self.mesh.number_of_cells()

    def number_of_local_dofs(self):
        return 11

    def interpolation_points(self):
        return self.dof.interpolation_points()

    def Forininterpolation_points(self):
        return self.dof.Forininterpolation_points()

    def cell_to_dof(self, index=np.s_[:]):
        return self.dof.cell_to_dof(index=index)

    def face_to_dof(self, index=np.s_[:]):
        return self.dof.face_to_dof(index=index)

    def edge_to_dof(self, index=np.s_[:]):
        return self.dof.edge_to_dof(index=index)

    def is_boundary_dof(self, threshold=None):
        return self.dof.is_boundary_dof(threshold=threshold)

    def geo_dimension(self):
        return self.GD

    def top_dimension(self):
        return self.TD

    

    @barycentric
    def face_basis(self, bc):
        ''' basis on a face '''

        phif = 2-3*np.sum(bc**2,-1) #(NQ,)
        phie = 4*bc[...,[1,2,0]]*bc[...,[2,0,1]] #(NQ,3)

        if len(bc.shape)==1:
            phi = np.concatenate([phie,[phif]])
        else:
            phi = np.vstack((phie.T,phif.T)).T        
        
        return phi[...,None,:] #(1,4) or (NQ,1,4)




    @barycentric
    def basis(self, bc):
        """
        compute the basis function values at barycentric point bc

        Parameters
        ----------
        bc : numpy.ndarray
            the shape of `bc` can be `(TD+1,)` or `(NQ, TD+1)`
        Returns
        -------
        phi : numpy.ndarray
            the shape of 'phi' can be `(1, ldof)` or `(NQ, 1, ldof)`
        """
        phie = 4*bc[...,[0,0,0,1,1,2]]*bc[...,[1,2,3,2,3,3]] #(NQ,6)

        phif = 2*(1-bc)**2-3*(bc[...,[1,2,3,0]]**2+bc[...,[2,3,0,1]]**2+bc[...,[3,0,1,2]]**2) #(NQ,4)
     
        #phif = 10*bc**2 - 8*bc + 1 #(NQ, 4)
    
        phic = 2-4*np.sum(bc**2,-1) #(NQ,1)
        if len(bc.shape)==1:
            phi = np.concatenate([phie,phif,[phic]])
        else:
            phi = np.vstack((phie.T,phif.T,phic.T)).T

       # print(phi[..., None, :].shape) #(1, ldof) or (NQ, 1, ldof)
        return phi[..., None, :] 

    @barycentric
    def grad_basis(self, bc, index=np.s_[:]):
        """
        compute the grad basis function values at barycentric point bc

        Parameters
        ----------
        bc : numpy.ndarray
            the shape of `bc` can be (TD+1, ) or `(NQ, TD+1)`

        Returns
        -------
        gphi : numpy.ndarray
            the shape of `gphi` can be `(NC, ldof, GD)' or
            `(NQ, NC, ldof, GD)'
        """
        mesh = self.mesh
        grad_lambda = mesh.grad_lambda()[index] #(NC, TD+1, GD)
        gphie = 4*(bc[...,None,[0,0,0,1,1,2],None]*grad_lambda[...,[1,2,3,2,3,3],:]
                    +bc[...,None,[1,2,3,2,3,3],None]*grad_lambda[...,[0,0,0,1,1,2],:])
        
        gphif = 4*(bc[...,None,:,None]-1)*grad_lambda - 6*(bc[...,None,[1,2,3,0],None]*grad_lambda[...,[1,2,3,0],:]
                                + bc[...,None,[2,3,0,1],None]*grad_lambda[...,[2,3,0,1],:]
                                +bc[...,None,[3,0,1,2],None]*grad_lambda[...,[3,0,1,2],:])
        '''
        gphif = 20*bc[...,None,:,None]*grad_lambda - 8*grad_lambda
        '''

        gphic = -8*np.sum(bc[...,None,:,None]*grad_lambda,-2)
        gphic = gphic[...,None,:]

        
        NQ = bc.shape[0]
        NC = grad_lambda.shape[0]
        ldof = self.number_of_local_dofs()
        GD = self.geo_dimension()
        if len(bc.shape) == 1:
            shape = (NC, ldof, GD)
        else:
            shape = (NQ,NC,ldof,GD)
        
        gphi = np.empty(shape)

        gphi[...,0:6,:] = gphie
        gphi[...,6:10,:] = gphif
        gphi[...,10:11,:] = gphic 
       # print(gphi.shape) #(NC, ldof, GD) or (NQ, NC, ldof, GD)
        return gphi

    @barycentric
    def value(self, uh, bc, index=np.s_[:]):
        phi = self.basis(bc) #phi.shape = (1,ldof) or (NQ,1,ldof)
        cell2dof = self.cell_to_dof()
        dim = len(uh.shape) - 1 #uh.shape = (gdof,) or 
        s0 = 'abcdefg'
        s1 = '...ij, ij{}->...i{}'.format(s0[:dim], s0[:dim])
        val = np.einsum(s1, phi, uh[cell2dof[index]])
       # print(uh[cell2dof], '\n', cell2dof)
        return val

    @barycentric
    def grad_value(self, uh, bc, index=np.s_[:]):
        gphi = self.grad_basis(bc, index=index) #(NC, ldof, GD) or (NQ, NC, ldof, GD)
        cell2dof = self.cell_to_dof()
        dim = len(uh.shape) - 1
        s0 = 'abcdefg'
        s1 = '...ijm, ij{}->...i{}m'.format(s0[:dim], s0[:dim])
        val = np.einsum(s1, gphi, uh[cell2dof[index]])
        return val

    def stiff_matrix(self, c=None):
        gdof = self.number_of_global_dofs()
        cell2dof = self.cell_to_dof()
        b0 = (self.grad_basis, cell2dof, gdof)
        q = 2 #gphi is pisecise linear
        A = self.integralalg.serial_construct_matrix(b0, c=c, q=q)
        return A

    def source_vector(self, f, dim=None, q=None):
        cellmeasure = self.cellmeasure
        bcs, ws = self.integrator.get_quadrature_points_and_weights()

        if f.coordtype == 'cartesian':
            pp = self.mesh.bc_to_point(bcs)
            fval = f(pp)
        elif f.coordtype == 'barycentric':
            fval = f(bcs)

       

        gdof = self.number_of_global_dofs()
        shape = gdof if dim is None else (gdof, dim)
        b = np.zeros(shape, dtype=self.ftype)

        if type(fval) in {float, int}:
            if favl == 0.0:
                return b
            else:
                phi = self.basis(bcs)
                bb = np.einsum('i, ijm, j->jm...',
                        ws, phi, self.cellmeasure)
                bb *=fval
        else:
            phi = self.basis(bcs)
            bb = bb = np.einsum('i, ij..., ijm, j->jm...',
                        ws, fval, phi, self.cellmeasure)
        cell2dof = self.cell_to_dof()
        if dim is None:
            np.add.at(b, cell2dof, bb)
        else:
            np.add.at(b, (cell2dof, np.s_[:]), bb)

        return b

    def interpolation(self, u, dim=None):
        ipoints = self.dof.interpolation_points()
        uI = u(ipoints)
        return self.function(dim=dim, array=uI)



    def Forininterpolation(self, u, dim=None):
        uI = self.Forininterpolationarray(u,dim=dim)
        return self.function(dim=dim, array=uI)

    def myinterpolation(self, u, dim=None):
        uI = self.myinterpolationarray(u,dim=dim)
        return self.function(dim=dim, array=uI)




    def myinterpolationarray(self,u,dim=None,index=np.s_[:]):
        ipoints = self.dof.Forininterpolation_points() #(NE+NN,3)
        uo = u(ipoints) #(NE+NN,)

        mesh = self.mesh

        NE = mesh.number_of_edges()
        NF = mesh.number_of_faces()
        NC = mesh.number_of_cells()

        uE = uo[:NE] #(NE,)     
        uN = uo[NE:] #(NN,)

        u_cell_node = uN[mesh.entity('cell')]    #(NC,4)
        u_face_node = uN[mesh.entity('face')]    #(NF,3)
        u_edge_node = uN[mesh.entity('edge')]    #(NE,2)

        uE = uE + 0.75*np.sum(u_edge_node,-1) #(NE,)
        uF = -0.5*np.sum(u_face_node,-1) #(NF,)
        uC = -1.25*np.sum(u_cell_node,-1) #(NC,)

        uI = np.hstack((uE,uF,uC))

        return uI[index]





    def Forininterpolationarray(self,u,dim=None,index=np.s_[:]):
        ipoints = self.dof.Forininterpolation_points() #(NE+NN,3)
        uo = u(ipoints) #(NE+NN,)

        mesh = self.mesh

        NE = mesh.number_of_edges()
        NF = mesh.number_of_faces()
        NC = mesh.number_of_cells()

        uE = uo[:NE] #(NE,)     
        uN = uo[NE:] #(NN,)

        u_cell_node = uN[mesh.entity('cell')]    #(NC,4)
        u_face_node = uN[mesh.entity('face')]    #(NF,3)
        u_edge_node = uN[mesh.entity('edge')]    #(NE,2)

        uE = uE + 0.75*np.sum(u_edge_node,-1) #(NE,)
        uF = -np.sum(u_face_node,-1) #(NF,)
        uC = np.sum(u_cell_node,-1) #(NC,)

        uI = np.hstack((uE,uF,uC))

        return uI[index]
        

    def function(self, dim=None, array=None):
        f = Function(self, dim=dim, array=array, coordtype='barycentric')
        return f

    def array(self, dim=None):
        gdof = self.number_of_global_dofs()
        if dim in {None, 1}:
            shape = gdof
        elif type(dim) is int:
            shape = (gdof, dim)
        elif type(dim) is tuple:
            shape = (gdof, ) + dim
        return np.zeros(shape, dtype=self.ftype)

    def integral_basis(self):
        """
        auxiliary pure neumann boundary
        """
        cell2dof = self.cell_to_dof()
        bcs, ws =self.integrator.get_quadrature_points_and_weights()
        phi = self.basis(bcs)
        cc = np.einsum('m, mik, i->ik', ws, phi, self.cellmeasure)
        gdof = self.number_of_global_dofs()
        c = np.zeros(gdof, dtype=self.ftype)
        np.add.at(c, cell2dof, cc)
        return c


    def set_dirichlet_bc(self, uh, g, threshold=None):
        ipoints = self.Forininterpolation_points()
        isBdDof = self.is_boundary_dof(threshold=threshold)  
        uh[isBdDof] = self.Forininterpolationarray(g,dim=None,index=isBdDof)
       # print(isBdDof.shape)       

        return isBdDof


    def set_neumann_bc(self, F, gN, threshold=None, q=None):
        '''
        设置 Neumann 边界条件到载荷矩阵 F 中
        '''

        mesh = self.mesh

        dim = 1 if len(F.shape)==1 else F.shae[1]

        if type(threshold) is np.ndarray:
            index = threshold
        else:
            index = self.mesh.ds.boundary_face_index()
            if threshold is not None:
                bc = self.mesh.entity_barycenter('face',index=index)
                flag = threshold(bc)
                index = index[flag]

        face2dof = self.face_to_dof()[index]
        n = mesh.face_unit_normal(index=index)
        measure = mesh.entity_measure('face', index=index)

        qf = self.integralalg.faceintegrator if q is None else mesh.integrator(q, 'face')
        bcs, ws = qf.get_quadrature_points_and_weights()
        phi = self.face_basis(bcs)

        pp = mesh.bc_to_point(bcs, etype='face', index=index)
        val = gN(pp, n) #(NQ, NF, ...), 假设 gN 是一个函数

        bb = np.einsum('m, mi..., mik, i->ik...', ws, val, phi, measure)
        if dim == 1:
            np.add.at(F, face2dof, bb)
        else:
            np.add.at(F, (face2dof, np.s_[:]), bb)



    def set_robin_bc(self, A, F, gR, threshold=None, q=None):
        """
        设置 Robin 边界条件到离散系统 Ax = b 中.
        """
        mesh = self.mesh
        dim = 1 if len(F.shape) == 1 else F.shape[1]

        if type(threshold) is np.ndarray:
            index = threshold
        else:
            index = self.mesh.ds.boundary_face_index()
            if threshold is not None:
                bc = self.mesh.entity_barycenter('face', index=index)
                flag = threshold(bc)
                index = index[flag]

        face2dof = self.face_to_dof()[index]
        print(index)
        qf = self.integralalg.faceintegrator if q is None else mesh.integrator(q, 'face')
        bcs, ws = qf.get_quadrature_points_and_weights()

        measure = mesh.entity_measure('face', index=index)

        phi = self.face_basis(bcs)
        pp = mesh.bc_to_point(bcs, etype='face', index=index)
        n = mesh.face_unit_normal(index=index)

        val, kappa = gR(pp, n) #(NQ, NF, ...)

        bb = np.einsum('m, mi..., mik, i->ik...', ws, val, phi, measure)
        if dim == 1:
            np.add.at(F, face2dof, bb)
        else:
            np.add.ta(F, (face2dof, np.s_[:]), bb)

        FM = np.einsum('m, mi, mij, mik, i->ijk', ws, kappa, phi, phi, measure)

        I = np.broadcast_to(face2dof[:, :, None], shape=FM.shape)
        J = np.broadcast_to(face2dof[:, None, :], shape=FM.shape)

        A += csr_matrix((FM.flat, (I.flat, J.flat)), shape=A.shape)

        return A, F       


        










###################################################################
if __name__ == '__main__':
    from fealpy.mesh import MeshFactory
    from fealpy.mesh.TetrahedronMesh import TetrahedronMesh
    import matplotlib.pyplot as plt
    import sympy as sp
    from mpl_toolkits.mplot3d import Axes3D
    from pde_model2 import generalelliptic3D
    import fealpy.boundarycondition as bdc
    from scipy.sparse.linalg import spsolve
    from fealpy.tools.show import showmultirate, show_error_table
    from fealpy.functionspace import LagrangeFiniteElementSpace

    #general pde model
    x, y, z = sp.symbols('x0,x1,x2')
    #u = sp.sin(sp.pi*x)*sp.sin(sp.pi*y)*sp.sin(sp.pi*z)-(2/sp.pi)**3
    #u = sp.sin(2*sp.pi*x)*sp.sin(2*sp.pi*y)*sp.sin(2*sp.pi*z)
    u = sp.sin(sp.pi*x)*sp.exp(x+y+z)
    #u = sp.cos(sp.pi*x)*sp.cos(sp.pi*y)*sp.cos(sp.pi*z)
    #u = (1-x-y-z)**5
    pde = generalelliptic3D(u,x,y,z,
          Dirichletbd='(x==1.0)|(x==0.0)|(y==1)|(y==0.0)',
          Neumannbd= '(z==0)|(z==1)')
    '''
    pde = generalelliptic3D(u,x,y,z,
          Neumannbd='(x==1.0)|(x==0.0)|(y==0.0)|(y==1)|(z==0)|(z==1)')
    '''

    mf = MeshFactory()
    '''
    node = np.array([
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [0.0, 0.0, -1.0]], dtype=np.float64)
    cell = np.array([
                [0, 1, 2, 3],
                [0, 1, 2, 4]], dtype=np.int_)
    mesh = TetrahedronMesh(node, cell)

    #mesh = mf.one_tetrahedron_mesh()

    
    spaceCRFortion = CRFortin3DFiniteElementSpace(mesh)
    spaceLagrange = LagrangeFiniteElementSpace(mesh,p=2)
   
   
    uICRFortin = spaceCRFortion.Forininterpolation(pde.solution)
    uILP2 = spaceLagrange.interpolation(pde.solution)
    exactu = sp.lambdify((x,y,z),u,'numpy')

    bc = np.array([0.5,0.2,0.2,0.1],dtype=mesh.ftype)
    bcs = mesh.bc_to_point(bc)

    print('interpoints=', bcs.squeeze(),
            '\n exactu=', exactu(bcs[...,0],bcs[...,1],bcs[...,2]).squeeze(),
            '\n LP2=',uILP2(bc).squeeze(),
            '\n CRFortoin=', uICRFortin(bc).squeeze())

    '''



   #load mesh
    domain = pde.domain()
    mesh = mf.boxmesh3d(domain, nx=1,ny=1,nz=1,meshtype='tet')



    NDof = np.zeros(4, dtype=mesh.itype)
    errormatrix = np.zeros((2,4),dtype = mesh.ftype)
    errortype = ['$||u-u_h||_0$', '$||\\nabla u-\\nabla u_h||_0$']


    for i in range(4):
        print('Step:', i)
        space = CRFortin3DFiniteElementSpace(mesh)   
        NDof[i] = space.number_of_global_dofs()
       
        uh = space.function()
        A = space.stiff_matrix()
        F = space.source_vector(pde.source)
        
        bc = bdc.NeumannBC(space, pde.neumann, threshold=pde.is_neumann_boundary)
        #A, F = bc.apply(F,A=A)
        # uh[:] = spsolve(A, F)[:-1] # pure neumann

        F = bc.apply(F)

        bc = bdc.RobinBC(space, pde.robin, threshold=pde.is_robin_boundary)

        A, F = bc.apply(A,F)

 
        bc = bdc.DirichletBC(space, pde.dirichlet, threshold=pde.is_dirichlet_boundary)
        A, F = bc.apply(A,F,uh)

        uh[:] = spsolve(A, F)

      

       # space.set_neumann_bc(F,pde.neumann,threshold=pde.is_neumann_boundary)




        #插值误差
        #uI = space.interpolation(pde.solution) #插值点给法有问题
        uI = space.Forininterpolation(pde.solution) # 重构建了P2插值，完美
        errormatrix[0, i] = space.integralalg.L2_error(pde.solution,  uh.value)
        errormatrix[1, i] = space.integralalg.L2_error(pde.gradient,  uh.grad_value)

        if i<3:
            mesh.uniform_refine()

    k = 0
    showmultirate(plt, k, NDof, errormatrix, errortype, propsize=20)
    show_error_table(NDof, errortype,  errormatrix)

    #plt.show()
 












'''
    #check the dof and interpolation point
    dof = CR_FortinDof(mesh)
    ipoints = dof.interpolation_points()
    cell2dof = dof.cell_to_dof()

    #check the phi and gphi
    qf = mesh.integrator(4, 'cell')
    bcs, ws = qf.get_quadrature_points_and_weights()
    bcs = np.array([1.0,0.0,0.0,0.0],dtype=mesh.ftype)
    phi = space.basis(bcs)
    gphi = space.grad_basis(bcs)
    grad_lambda = mesh.grad_lambda()

    np.set_printoptions(precision=3)

    print('bc = ', bcs.squeeze(), 
        '\n phi = ', phi.squeeze(),
        '\n gphi = ', gphi.squeeze(),
        '\n grad_lambda = \n', grad_lambda.squeeze())

 
    #print(cell2dof.shape, phi.shape, gphi.shape)

    #check the value and grad_value
    gdof = space.number_of_global_dofs()
    uh = np.random.random((gdof,2))
    uhs = space.value(uh,bcs)
    guhs = space.grad_value(uh,bcs)

   # print(bcs.shape,cell2dof.shape,uh.shape,uhs.shape,guhs.shape)

'''

 

















'''


node = mesh.entity('node')
cell = mesh.entity('cell')
face = mesh.entity('face')
edge = mesh.entity('edge')

cell2face = mesh.ds.cell_to_face()
cell2edge = mesh.ds.cell_to_edge()

#print(cell2edge,'\n\n', edge)

#print(cell2dof)

fig = plt.figure()
axes = Axes3D(fig)
mesh.add_plot(axes)


#mesh.find_node(axes, showindex=True, color='b', fontsize=30)
#mesh.find_edge(axes, showindex=True, color='g', fontsize=24)
#mesh.find_face(axes, showindex=True, fontsize=22)
#mesh.find_cell(axes, showindex=True, fontsize=20)
ipoints = spaceCRFortion.interpolation_points()
#mesh.find_node(axes, showindex=True, color='b', fontsize=2)
mesh.find_node(axes, node=ipoints, showindex=True, color='r', fontsize=30)
plt.show()


'''
#在要求边界P1投影为0下，只能解齐次dirichlet,非齐次的不能解, 因为边界投影自由度不够
