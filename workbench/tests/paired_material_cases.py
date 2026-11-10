"""Bounded saved pair-material runtime fixture; not a physical reference."""
from sipi import PairImpedanceDesignDocument
from sipi.dielectric import ConstantDielectric, PrincipalAxisDielectric


def pair_material_goal():
    return PairImpedanceDesignDocument('coupled_stripline',
        dict(width=.3e-3, gap=.3e-3, plane_spacing=1e-3, eps_r=1, box_width=.006),
        variables=['x', 'y'], bounds=[[2, 6], [2, 6]], initial=[3, 3],
        targets=dict(z_diff=100., z_common=34.), tolerances=dict(z_diff=1., z_common=.5),
        mesh=dict(edge_size=5e-6, far_size=.125e-3, grade=.15), frequency=1e8,
        materials={'dielectric': PrincipalAxisDielectric(
            ConstantDielectric(3, .01), ConstantDielectric(3, .02), 0)},
        material_variables={name: dict(region='dielectric', path=[axis, 'parameters', 'eps_r'])
            for name, axis in [('x', 'axis1'), ('y', 'axis2')]}, max_evaluations=64)


def material_study(kind):
    from sipi.study import ImpedanceStudyDocument
    from sipi.dielectric import DebyeDielectric
    if kind not in ('constant', 'debye', 'tensor', 'mixed-normal'):
        raise ValueError('unknown material study fixture')
    parameters = dict(width=.3e-3, plane_spacing=1e-3, eps_r=1, box_width=.006)
    model = DebyeDielectric(2, [4], [1e8]) if kind == 'debye' else ConstantDielectric(4, .01)
    binding = {'dk': dict(region='dielectric', path=['strengths', 0] if kind == 'debye' else ['eps_r'])}
    sampling = dict(kind='sweep', count=6 if kind == 'debye' else 8,
        variables=[dict(name='dk', lower=1 if kind == 'debye' else 2, upper=6)])
    if kind == 'tensor':
        parameters['gap'] = .3e-3
        model = PrincipalAxisDielectric(ConstantDielectric(3, .01), ConstantDielectric(5, .02), 0)
        binding = {name: dict(region='dielectric', path=[axis, 'parameters', 'eps_r'])
            for name, axis in [('x', 'axis1'), ('y', 'axis2')]}
        sampling = dict(kind='normal', count=8, seed=91, correlation=[[1, .5], [.5, 1]],
            variables=[dict(name='x', mean=3, std=.1), dict(name='y', mean=5, std=.2)])
    elif kind == 'mixed-normal':
        sampling = dict(kind='normal', count=4, seed=9, correlation=[[1]],
            variables=[dict(name='dk', mean=2, std=2)])
    return ImpedanceStudyDocument('coupled_stripline' if kind == 'tensor' else 'stripline',
        parameters, quantity='z_diff' if kind == 'tensor' else 'z0', sampling=sampling,
        mesh=dict(edge_size=5e-6, far_size=.125e-3, grade=.15), frequency=1e8,
        materials={'dielectric': model}, material_variables=binding)
