"""Bounded material-target inputs shared by native and actual browser checks."""
from sipi import ImpedanceDesignDocument
from sipi.dielectric import ConstantDielectric, DebyeDielectric


def material_goal(kind):
    if kind == 'constant':
        model, path = ConstantDielectric(4, .01), ['eps_r']
    elif kind == 'debye':
        model, path = DebyeDielectric(2, [4], [1e8]), ['strengths', 0]
    else:
        raise ValueError('unknown material goal fixture')
    return ImpedanceDesignDocument('stripline',
        dict(width=.5e-3, plane_spacing=1e-3, eps_r=1, box_width=.006),
        variable='material', bounds=[2, 8], target=50., tolerance=1.,
        mesh=dict(edge_size=5e-6, far_size=.125e-3, grade=.15),
        frequency=1e8, materials={'dielectric': model},
        material_variables={'material': dict(region='dielectric', path=path)})
