"""Inputs for actual native/browser saved-analysis acceptance."""
import json
from sipi import (LumpedNetworkDocument, EllipticalAperture, RoundConductor,
    ApertureSectionDocument, ApertureStudyDocument, ApertureDesignDocument,
    CrossSectionDocument, ImpedanceDesignDocument, microstrip)
from sipi.line_model import TransmissionLineDocument
from sipi.execution import execute_saved

aperture = ApertureSectionDocument(EllipticalAperture(.8e-3, .8e-3,
    [RoundConductor('s', .28e-3)], eps_r=3.96), mesh=dict(size=.1e-3, angular_divisions=16))
lumped = LumpedNetworkDocument([0, 1e9], resistance=10, inductance=2e-9)
study = ApertureStudyDocument(aperture, sampling=dict(kind='normal', count=3, seed=771,
    variables=[dict(name='width', mean=.8e-3, std=1e-3)], correlation=[[1.]]))
goal = ApertureDesignDocument(aperture, variable='conductor_0_diameter',
    bounds=[.2e-3, .35e-3], target=200e-12, tolerance=1e-14)
# Deliberately overfine input reaches the original point budget. No patched
# mesher limit or fabricated numerical failure is used by either runtime.
mesh_goal = ImpedanceDesignDocument('stripline',
    dict(width=.3e-3, plane_spacing=1e-3, eps_r=4, box_width=6e-3),
    variable='width', bounds=[.2e-3, .4e-3], target=50., tolerance=.1,
    mesh=dict(edge_size=1e-12, far_size=.2e-3, grade=.2))
line = TransmissionLineDocument(CrossSectionDocument(microstrip(width=.4e-3,
    substrate_height=.5e-3, eps_r=4, air_height=.5e-3, box_width=2e-3),
    mesh=dict(edge_size=20e-6, far_size=.2e-3, grade=.2)), [0, 1e3],
    materials={}, conductor={'kind':'perfect'}, length=.01)
from galerkin.mesh3d import box_mesh
from sipi.capacitance3d_document import Capacitance3DDocument
import numpy as np
mesh = box_mesh(.004, .003, .002, 4, 4, 4)
capacitance3d = []
for layered in (False, True):
    eps = np.where(mesh.nodes[mesh.tets].mean(axis=1)[:, 2] < .001, 2., 6.) if layered else 3.8
    doc = Capacitance3DDocument(mesh, eps_r=eps,
        conductors={'top': mesh.boundary['z1']}, ground=mesh.boundary['z0'])
    text = json.dumps(doc.to_dict(), separators=(',', ':'))
    capacitance3d.append(dict(name='layered' if layered else 'uniform', text=text, expected=execute_saved(text)))
x, y, z = mesh.nodes.T
signals = {'right': np.flatnonzero(np.isclose(x, .003)&np.isclose(y, .0015)&np.isclose(z, .001)),
           'left': np.flatnonzero(np.isclose(x, .001)&np.isclose(y, .0015)&np.isclose(z, .001))}
doc = Capacitance3DDocument(mesh, eps_r=3.8, conductors=signals,
    ground=np.unique(np.concatenate(list(mesh.boundary.values()))))
text = json.dumps(doc.to_dict(), separators=(',', ':'))
capacitance3d.append(dict(name='two-internal-nodal-electrodes', text=text, expected=execute_saved(text)))
from material_goal_cases import material_goal
material_goals = []
for kind in ('constant', 'debye'):
    text = material_goal(kind).dumps()
    material_goals.append(dict(name=kind, text=text, expected=execute_saved(text)))

print(json.dumps(dict(lumped=lumped.dumps(), study=study.dumps(), goal=goal.dumps(),
                     mesh_goal=mesh_goal.dumps(), material_goals=material_goals,
                     line=line.dumps(), expected=execute_saved(lumped.dumps()),
                     capacitance3d=capacitance3d), allow_nan=False))
