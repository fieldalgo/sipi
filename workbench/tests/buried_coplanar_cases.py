"""Buried coplanar editable inputs; fixture generation never solves."""
from sipi.template_document import TemplateSectionDocument
NAMES=('coplanar_stripline','coupled_coplanar_stripline')
COARSE=dict(edge_size=10e-6,far_size=.25e-3,grade=.3,min_angle=28)
FINE=dict(edge_size=5e-6,far_size=.125e-3,grade=.15,min_angle=28)
def parameters(name,*,vacuum=False):
 p=dict(width=.0003000000000123456,gap=.0003,ground_width=.0008,plane_spacing=.001,
  trace_height=.0004000000000123456,eps_r=4.,thickness=.000035,tan_delta=.02,box_width=.006,top_width=.00025)
 if name==NAMES[1]:p['ground_gap']=.0003
 if vacuum:p.update(eps_r=1.,tan_delta=0.,top_width=None,thickness=0.)
 return p
def editable(name,*,vacuum=False):return TemplateSectionDocument(name,parameters(name,vacuum=vacuum),mesh=COARSE).to_dict()
if __name__=='__main__':
 import json
 print(json.dumps({name:editable(name) for name in NAMES}))
