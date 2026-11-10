"""Small normal-film coplanar inputs; fixtures never run a field solve."""
from sipi.template_document import TemplateSectionDocument

NAMES = ('conformal_coated_unbacked_coplanar', 'coupled_conformal_coated_unbacked_coplanar')
COARSE = dict(edge_size=4e-6, far_size=.00025, grade=.2, min_angle=28)


def parameters(name, *, vacuum=False):
    p = dict(width=.0005, substrate_height=.0005, eps_r=4., thickness=.000035,
             top_width=.0004, tan_delta=.01, coating_thickness=.000020000000000123456,
             coating_eps_r=3.5, coating_tan_delta=.02, air_height=.006, lower_air_height=.006000000000123456, box_width=.012, gap=.0002, ground_width=.001)
    if name == NAMES[1]:
        p.update(gap=.0003, ground_gap=.0002)
    if vacuum:
        p.update(eps_r=1., thickness=0., top_width=None, tan_delta=0.,
                 coating_eps_r=1., coating_tan_delta=0., coating_thickness=.00002,
                 air_height=.012, lower_air_height=.012, box_width=.024)
    return p


def editable(name, *, vacuum=False):
    return TemplateSectionDocument(name, parameters(name, vacuum=vacuum), mesh=COARSE).to_dict()


if __name__ == '__main__':
    import json
    print(json.dumps({name: editable(name) for name in NAMES}))
