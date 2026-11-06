# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Do not turn roundoff-scale film gaps into impractically small default meshes."""
import pytest
from shapely.geometry import Polygon
from sipi import CrossSection,templates

NAMES=('conformal_coated_microstrip','coupled_conformal_coated_microstrip',
       'conformal_coated_grounded_coplanar','coupled_conformal_coated_grounded_coplanar',
       'conformal_coated_unbacked_coplanar','coupled_conformal_coated_unbacked_coplanar')
PAIRS=tuple(name for name in NAMES if name.startswith('coupled_'))


def params(name,**changes):
    p=dict(width=.5e-3,substrate_height=.5e-3,eps_r=4,thickness=35e-6,
           coating_thickness=20e-6,coating_eps_r=3.5)
    if 'coplanar' in name:p.update(gap=.2e-3,ground_width=1e-3)
    if name.startswith('coupled_'):
        p['gap']=.3e-3
        if 'coplanar' in name:p['ground_gap']=.2e-3
    p.update(changes);return p


@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('change',[dict(coating_thickness=1e-15),dict(air_height=1e-15),
                                  dict(thickness=1e-15),dict(top_width=1e-15)])
def test_unresolved_positive_features_fail_before_meshing(name,change,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('invalid geometry must not mesh')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError,match='features must exceed'):
        getattr(templates,name)(**params(name,**change))


@pytest.mark.parametrize('name',PAIRS)
def test_real_subresolution_air_slit_is_rejected_not_snapped(name):
    p=params(name,gap=40e-6*(1+1e-12))
    with pytest.raises(ValueError,match='features must exceed'):
        getattr(templates,name)(**p)


@pytest.mark.parametrize('name',NAMES[4:])
def test_lower_air_must_be_resolved_after_translating_the_film(name):
    with pytest.raises(ValueError,match='features must exceed'):
        getattr(templates,name)(**params(name,lower_air_height=1e-15))


@pytest.mark.parametrize('name',PAIRS)
@pytest.mark.parametrize('factor',[1-1e-12,1.])
def test_exact_contact_and_overlap_remove_only_redundant_seams(name,factor,monkeypatch):
    import shapely.ops
    original_union=shapely.ops.unary_union;captured=[]
    def capture(shapes):
        result=original_union(shapes);captured.append(result);return result
    monkeypatch.setattr(shapely.ops,'unary_union',capture)
    p=params(name,gap=40e-6*factor)
    if 'coplanar' in name:p['ground_gap']=40e-6*factor
    section=getattr(templates,name)(**p);film=section.dielectric_regions[0]._shape
    d=p['coating_thickness'];assert len(captured)==1
    # Compare cleanup with its exact input coordinates, not a recomputation
    # with differently rounded angle/translation arithmetic. Independent film
    # area and normal-distance identities are checked in the geometry suites.
    original=captured[0]
    if 'unbacked' in name:
        lower=section.layers[0].thickness
        original=Polygon([(x,y+lower) for x,y in original.exterior.coords])
    assert original.equals(film) and original.symmetric_difference(film).area==0
    assert film.minimum_clearance==pytest.approx(d,rel=1e-10)
    assert section._sizes(None,None)[0]==pytest.approx(d/100,rel=1e-10)


@pytest.mark.parametrize('name',NAMES)
def test_zero_metal_thickness_and_resolved_air_gap_remain_valid(name):
    thin=getattr(templates,name)(**params(name,thickness=0))
    assert all(t.thickness==0 for t in thin.traces)
    assert thin.dielectric_regions[0].minimum_dimension>1e-6
    if name in PAIRS:
        p=params(name,gap=50e-6)
        section=getattr(templates,name)(**p)
        # A real ten-micrometre air slit is retained, not bridged.
        film=section.dielectric_regions[0]._shape
        from shapely.geometry import Point
        h=section.traces[0].y
        assert not film.covers(Point(0,h+p['coating_thickness']+p['thickness']/2))
