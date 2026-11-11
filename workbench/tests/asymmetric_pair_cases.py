"""Unequal widths, copper thicknesses and profiles with explicit conductor order."""
import json
from sipi.template_document import TemplateSectionDocument
NAMES=('asymmetric_coupled_microstrip','asymmetric_coupled_stripline')
COARSE=dict(edge_size=5e-6,far_size=.00025,grade=.2,min_angle=28)
def parameters(name,**changes):
 buried=name==NAMES[1]
 p=dict(left_width=(.0003 if buried else .0004)+1.23456e-14,
        right_width=(.0005 if buried else .00065)+1.23456e-14,
        left_thickness=.000035,right_thickness=.00005,
        left_top_width=(.00025 if buried else .00032)+1.23456e-14,
        right_top_width=(.00045 if buried else .00055)+1.23456e-14,
        gap=(.0004 if buried else .00025)+1.23456e-14,eps_r=4.,tan_delta=.02,
        box_width=.006 if buried else .012)
 p['plane_spacing' if buried else 'substrate_height']=.0010000000000123456 if buried else .0005000000000123456
 if not buried:p['air_height']=.0060000000000123456
 return {**p,**changes}
if __name__=='__main__':
 print(json.dumps({n:TemplateSectionDocument(n,parameters(n),mesh=COARSE).to_dict() for n in NAMES}))
