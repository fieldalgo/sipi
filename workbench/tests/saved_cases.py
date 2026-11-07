"""Inputs for actual native/browser saved-analysis acceptance."""
import json
from sipi import (LumpedNetworkDocument, EllipticalAperture, RoundConductor,
    ApertureSectionDocument, ApertureStudyDocument, ApertureDesignDocument,
    CrossSectionDocument, microstrip)
from sipi.line_model import TransmissionLineDocument
from sipi.execution import execute_saved

aperture = ApertureSectionDocument(EllipticalAperture(.8e-3, .8e-3,
    [RoundConductor('s', .28e-3)], eps_r=3.96), mesh=dict(size=.1e-3, angular_divisions=16))
lumped = LumpedNetworkDocument([0, 1e9], resistance=10, inductance=2e-9)
study = ApertureStudyDocument(aperture, sampling=dict(kind='normal', count=3, seed=771,
    variables=[dict(name='width', mean=.8e-3, std=1e-3)], correlation=[[1.]]))
goal = ApertureDesignDocument(aperture, variable='conductor_0_diameter',
    bounds=[.2e-3, .35e-3], target=200e-12, tolerance=1e-14)
line = TransmissionLineDocument(CrossSectionDocument(microstrip(width=.4e-3,
    substrate_height=.5e-3, eps_r=4, air_height=.5e-3, box_width=2e-3),
    mesh=dict(edge_size=20e-6, far_size=.2e-3, grade=.2)), [0, 1e3],
    materials={}, conductor={'kind':'perfect'}, length=.01)
print(json.dumps(dict(lumped=lumped.dumps(), study=study.dumps(), goal=goal.dumps(),
                     line=line.dumps(), expected=execute_saved(lumped.dumps())), allow_nan=False))
