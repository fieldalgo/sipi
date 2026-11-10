"""Homogeneous broadside fixtures; generation never solves."""
from sipi.template_document import TemplateSectionDocument
NAME='broadside_stripline'
COARSE=dict(edge_size=10e-6,far_size=.25e-3,grade=.3,min_angle=28)
def parameters(**changes):
 return dict(dict(width=.0003000000000123456,gap=.0002000000000123456,
  plane_spacing=.001,thickness=.000035,offset=-.0001000000000123456,
  eps_r=4.,tan_delta=.02,box_width=.006),**changes)
def editable(**changes):return TemplateSectionDocument(NAME,parameters(**changes),mesh=COARSE).to_dict()
if __name__=='__main__':
 import json
 print(json.dumps(editable()))
