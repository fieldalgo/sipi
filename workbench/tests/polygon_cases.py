"""Existing geometry contracts for display/import qualification, without solves."""
import json
from sipi import (CrossSection, CrossSectionDocument, Layer, Trace, PolygonTrace,
                  DielectricRegion, conformal_coated_microstrip)

mesh = dict(edge_size=10e-6, far_size=.2e-3, grade=.15)
vertices = [[-.00035,.0008],[.00035,.0008],[.00025,.0012],
            [0,.0012],[0,.00105],[-.00035,.00105]]
region = [[-.0006,.0007],[.0006,.0007],[.0006,.0014],[-.0006,.0014]]
cases = {}
for clockwise in (False, True):
    section = CrossSection([Layer('lower',.001,4,.01),Layer('upper',.001,2,.02)],
        [PolygonTrace('signal', vertices[::-1] if clockwise else vertices)],.004,
        top='ground',dielectric_regions=[DielectricRegion('local film',region,3,.03)])
    cases['clockwise' if clockwise else 'concave'] = CrossSectionDocument(section,mesh=mesh).to_dict()

section = CrossSection([Layer('dielectric',.002,4,.01)], [
    PolygonTrace('left', [[-.0007,.0008],[-.0002,.0008],[-.0002,.001],[-.0007,.001]]),
    Trace('right', .00045,.0008,.0005,.0002,top_width=.0004),
    PolygonTrace('side ground',[[.0012,.0006],[.0015,.0006],[.0015,.0014]],ground=True)],
    .004,top='ground',dielectric_regions=[DielectricRegion('local film',region,3,.03)])
cases['asymmetric-pair'] = CrossSectionDocument(section,mesh=mesh).to_dict()

film = conformal_coated_microstrip(width=.0005,substrate_height=.0005,eps_r=4,
    thickness=.000035,top_width=.0004,coating_thickness=.00002,
    coating_eps_r=3.5,coating_tan_delta=.02,air_height=.004,box_width=.008)
cases['normal-film'] = CrossSectionDocument(film,mesh=dict(edge_size=4e-6,far_size=.00025,grade=.2)).to_dict()
if __name__ == '__main__':
    print(json.dumps(cases,allow_nan=False))
