"""Two explicit dielectric layers and copper extending above the interface."""
import json
from sipi.template_document import TemplateSectionDocument
NAMES=('layered_coplanar_stripline','coupled_layered_coplanar_stripline')
COARSE=dict(edge_size=1e-5,far_size=.00025,grade=.3,min_angle=28)
def parameters(name,**changes):
 p=dict(width=.0003000000000123456,lower_height=.0004000000000123456,
        upper_height=.0006000000000123456,lower_eps_r=3.8,upper_eps_r=4.5,
        thickness=.000035,lower_tan_delta=.01,upper_tan_delta=.02,
        box_width=.012,gap=.0002000000000123456,ground_width=.0010000000000123456,top_width=.0002500000000123456)
 if name==NAMES[1]:p['ground_gap']=.0002000000000123456
 return {**p,**changes}
if __name__=='__main__':
 print(json.dumps({name:TemplateSectionDocument(name,parameters(name),mesh=COARSE).to_dict() for name in NAMES}))
