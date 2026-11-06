# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Normal-thickness films on finite coplanar signals/grounds and saved inputs."""
import importlib.metadata as metadata

import numpy as np
import pytest
from scipy.constants import c,epsilon_0
from shapely.affinity import scale,translate
from shapely.geometry import LineString
from shapely.ops import unary_union

from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import CrossSectionDocument,ImpedanceDesignDocument,Layer,templates
from sipi.dielectric import ConstantDielectric,PrincipalAxisDielectric,dispersive_line
from sipi.line_model import TransmissionLineDocument
from sipi.polygons import trace_shape
from sipi.study import ImpedanceStudyDocument
from test_coupled_coplanar import panel_reference
from test_unbacked_coplanar import free_space_panels

NAMES=('conformal_coated_grounded_coplanar','coupled_conformal_coated_grounded_coplanar',
       'conformal_coated_unbacked_coplanar','coupled_conformal_coated_unbacked_coplanar')
COARSE=dict(edge_size=4e-6,far_size=.25e-3,grade=.2)
FINE=dict(edge_size=1e-6,far_size=.125e-3,grade=.1)


def params(name,**changes):
    p=dict(width=.5e-3,gap=.2e-3,ground_width=1e-3,substrate_height=.5e-3,
           eps_r=4,thickness=35e-6,top_width=.4e-3,tan_delta=.01,
           coating_thickness=20e-6,coating_eps_r=3.5,coating_tan_delta=.02,
           air_height=6e-3,box_width=12e-3)
    if name.startswith('coupled_'):p.update(gap=.3e-3,ground_gap=.2e-3)
    if 'unbacked' in name:p['lower_air_height']=6e-3
    p.update(changes);return p


def section(name,**changes):return getattr(templates,name)(**params(name,**changes))


def modes(line):
    if len(line.names)==1:return np.array([line.z0])
    m=line.even_odd();return np.array([m['z_even'],m['z_odd']])


def panel_modes(name,count):
    intervals=([(-.25,.25),(-1.45,-.45),(.45,1.45)] if not name.startswith('coupled_') else
               [(-.65,-.15),(.15,.65),(-1.85,-.85),(.85,1.85)])
    cap=(free_space_panels(intervals,count) if 'unbacked' in name else
         panel_reference([(a*1e-3,b*1e-3) for a,b in intervals],.5e-3,count))
    modal=[cap[0,0]] if not name.startswith('coupled_') else [cap[0,0]+cap[0,1],cap[0,0]-cap[0,1]]
    return 1/(c*np.array(modal))


@pytest.mark.parametrize('name',NAMES)
def test_every_ground_is_coated_exact_area_normal_distance_and_frame(name):
    p=params(name);cs=section(name);film=cs.dielectric_regions[0]._shape
    metal=unary_union([trace_shape(t) for t in cs.traces]);d=p['coating_thickness']
    expected=cs.width*d;lower=p.get('lower_air_height',0.)
    for trace in cs.traces:
        top=trace.width if trace.top_width is None else trace.top_width
        slope=(trace.width-top)/(2*trace.thickness)
        delta=d/(np.hypot(1,slope)+slope)
        expected+=2*delta*trace.thickness
        cut=film.intersection(LineString([(trace.x-trace.width,trace.y+d+trace.thickness/2),
                                         (trace.x,trace.y+d+trace.thickness/2)]))
        # Restrict to the envelope of this trace, separate from its neighbours.
        segment=max(list(cut.geoms) if hasattr(cut,'geoms') else [cut],key=lambda q:q.bounds[2])
        x=segment.bounds[0];y=trace.y+d+trace.thickness/2
        assert abs(x-slope*(y-trace.y)-(trace.x-trace.width/2))/np.hypot(1,slope)==pytest.approx(d,rel=1e-11)
        assert film.covers(trace_shape(trace))
        assert trace.y==pytest.approx(lower+p['substrate_height'],rel=1e-12)
        if trace.ground:assert trace.top_width is None
    assert len([t for t in cs.traces if t.ground])==2
    assert film.difference(metal).area==pytest.approx(expected,rel=1e-11)
    assert film.bounds[1]==pytest.approx(lower+p['substrate_height'],rel=1e-12)
    assert cs.height-film.bounds[3]==pytest.approx(p['air_height'],rel=1e-12)
    assert cs.bottom==('open' if 'unbacked' in name else 'ground') and cs.top=='open'
    assert film.symmetric_difference(scale(film,xfact=-1,yfact=1,origin=(0,0))).area<1e-12*film.area


@pytest.mark.parametrize('name',NAMES[2:])
def test_lower_air_translates_local_region_and_conductors_together(name):
    a,b=section(name,lower_air_height=1e-3),section(name,lower_air_height=2e-3)
    fa,fb=a.dielectric_regions[0]._shape,b.dielectric_regions[0]._shape
    assert translate(fa,yoff=1e-3).symmetric_difference(fb).area<1e-12*fa.area
    for ta,tb in zip(a.traces,b.traces):
        assert tb.y-ta.y==pytest.approx(1e-3,rel=1e-12)
        assert ta.x==tb.x and ta.width==tb.width and ta.ground==tb.ground
    assert a.layers[0]==Layer('lower_air',1e-3)


@pytest.mark.parametrize('name',NAMES)
def test_thin_vacuum_independent_panels_and_refinement(name):
    p=dict(eps_r=1,tan_delta=0,coating_eps_r=1,coating_tan_delta=0,
           thickness=0,top_width=None,air_height=12e-3,box_width=24e-3)
    if 'unbacked' in name:p['lower_air_height']=12e-3
    exact=panel_modes(name,160)
    np.testing.assert_allclose(panel_modes(name,80),exact,rtol=.003)
    values=[modes(section(name,**p).analyze(**dict(m,far_size=2*m['far_size']))) for m in (COARSE,FINE)]
    errors=[abs(v/exact-1) for v in values]
    print(name,'panel reference',exact,'vacuum errors',errors)
    assert np.all(errors[1]<.02) and np.all(errors[1]<errors[0])


@pytest.mark.parametrize('name',NAMES)
def test_complex_field_reference_and_separate_mesh_outer_convergence(name):
    skfem=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    cs=section(name);m=cs.mesh(**COARSE);clock=Stopwatch()
    with clock('openphysics'):actual=m.line_parameters();cc=actual.C-1j*actual.C_loss
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u,v,w):return w.eps*dot(grad(u),grad(v))
        k=skfem.asm(form,basis,eps=(m.eps_r*(1-1j*m.tan_delta))[:,None])
        fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]));fields=[]
        for nodes in m.signals.values():
            v=np.zeros(basis.N,complex);v[nodes]=1
            fields.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
        u=np.array(fields).T;expected=epsilon_0*(u.T@(k@u))
    error=float(abs(cc/expected-1).max())
    record=make_record(case=name,physics='normal-thickness film on finite coplanar traces',
        api='sipi.'+name,discretization='exact local film polygon and conforming P1 regions',
        tool='scikit-fem',tool_discretization='independent complex P1 assembly and energy',
        matched=['same mesh, metal priority, lossy substrate/film and finite coplanar grounds',
                 'backing plane present only for grounded variants'],
        not_matched=['no measured deposition, rounded corners or 3D fields'],
        observables=[observable('complex C','F/m','max relative difference',error,1e-9)],
        analytical_acceptance='normal-distance/area, vacuum panels, planar/air limits and mesh/domain studies',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<1e-9
    fine=cs.analyze(**FINE)
    outer=dict(box_width=24e-3,air_height=12e-3)
    if 'unbacked' in name:outer['lower_air_height']=12e-3
    wide=section(name,**outer).analyze(**FINE)
    fc=fine.C-1j*fine.C_loss;wc=wide.C-1j*wide.C_loss
    changes=float(abs(cc/fc-1).max()),float(abs(wc/fc-1).max())
    print(name,'complex C mesh/outer',changes)
    assert max(changes)<.01 and np.linalg.eigvalsh(fine.C_loss).min()>0


@pytest.mark.parametrize('name',NAMES)
def test_air_equivalent_and_zero_thickness_planar_limits(name):
    p=params(name,coating_eps_r=1,coating_tan_delta=0)
    coated=getattr(templates,name)(**p).analyze(**FINE)
    bare={k:v for k,v in p.items() if not k.startswith('coating_')}
    bare['air_height']+=p['thickness']+p['coating_thickness']
    original=getattr(templates,name.replace('conformal_coated_',''))(**bare).analyze(**FINE)
    np.testing.assert_allclose(coated.C-1j*coated.C_loss,original.C-1j*original.C_loss,rtol=.005,atol=0)
    thin=params(name,thickness=0,top_width=None)
    a=getattr(templates,name)(**thin).analyze(**FINE)
    thin['coating_height']=thin.pop('coating_thickness')
    b=getattr(templates,name.replace('conformal_',''))(**thin).analyze(**FINE)
    np.testing.assert_allclose(a.C-1j*a.C_loss,b.C-1j*b.C_loss,rtol=.005,atol=0)


@pytest.mark.parametrize('name',NAMES)
def test_saved_geometry_and_principal_material_override(name):
    cs=section(name);geometry=CrossSectionDocument(cs,mesh=COARSE)
    assert CrossSectionDocument.loads(geometry.dumps()).dumps()==geometry.dumps()
    assert geometry.to_dict()['schema']=='sipi.cross-section/3'
    material=ConstantDielectric(3.5,.02)
    doc=TransmissionLineDocument(geometry,[1e6,1e9],
        materials={'coating':PrincipalAxisDielectric(material,material,.4)},
        conductor={'kind':'perfect'},length=.01)
    result=TransmissionLineDocument.loads(doc.dumps()).analyze();static=geometry.analyze()
    np.testing.assert_allclose(result.C,np.broadcast_to(static.C,result.C.shape),rtol=1e-10,atol=0)
    np.testing.assert_allclose(result.dielectric.C_complex.imag,
        np.broadcast_to(-static.C_loss,result.C.shape),rtol=1e-10,atol=0)


@pytest.mark.parametrize('name',NAMES)
def test_correlated_geometry_study_preserves_materials_and_pair_pitch(name):
    pair=name.startswith('coupled_');p=params(name)
    material=PrincipalAxisDielectric(ConstantDielectric(2.5,.01),ConstantDielectric(4,.02))
    plan=ImpedanceStudyDocument(name,p,mesh=COARSE,quantity='z_diff' if pair else 'z0',
        sampling=dict(kind='normal',count=2,seed=881,correlation=[[1,-.4],[-.4,1]],
            variables=[dict(name='width',mean=.5e-3,std=10e-6),
                       dict(name='coating_thickness',mean=20e-6,std=2e-6)]),
        fixed_pitch_m=.8e-3 if pair else None,frequency=1e8,materials={'coating':material})
    replay=ImpedanceStudyDocument.loads(plan.dumps())
    np.testing.assert_array_equal(plan.samples(),replay.samples())
    result=replay.analyze();assert result.failed==0 and result.summary is not None
    for row in result.rows:
        if pair:assert row.parameters['width']+row.parameters['gap']==pytest.approx(.8e-3,rel=1e-12)
        sweep=dispersive_line(row.document.section,[1e8],materials={'coating':material},**row.document.mesh_options)
        v=np.array([1,-1]) if pair else np.ones(1)
        z=(2 if pair else 1)*np.sqrt((v@sweep.L@v)/(v@sweep.C[0]@v))
        assert row.impedance==pytest.approx(z,rel=1e-10)


@pytest.mark.parametrize('name',NAMES)
def test_saved_width_goal_passes_requested_and_refined_mesh(name):
    pair=name.startswith('coupled_')
    doc=ImpedanceDesignDocument(name,params(name,top_width=None),variable='width',
        bounds=[.2e-3,1.2e-3],quantity='z_diff' if pair else 'z0',target=100 if pair else 60,
        tolerance=1,max_evaluations=24,mesh=COARSE)
    result=ImpedanceDesignDocument.loads(doc.dumps()).solve()
    assert abs(result.residual)<=1 and abs(result.refined_residual)<=1
    assert result.document.to_dict()['schema']=='sipi.cross-section/3'
    print(name,'width goal',result.parameter,result.residual,result.refined_residual)


@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('change',[dict(gap=0),dict(ground_width=True),dict(coating_thickness=0),
    dict(coating_eps_r=.5),dict(coating_tan_delta=-1),dict(top_width=.6e-3),
    dict(air_height=0),dict(box_width=1e-3)])
def test_invalid_physical_inputs(name,change):
    with pytest.raises(ValueError):section(name,**change)


@pytest.mark.parametrize('name',NAMES[2:])
@pytest.mark.parametrize('lower',[0,-1,True,np.nan])
def test_invalid_lower_air(name,lower):
    with pytest.raises(ValueError):section(name,lower_air_height=lower)


@pytest.mark.parametrize('name',[NAMES[1],NAMES[3]])
def test_ground_gap_is_not_signal_gap_and_small_gaps_merge_film(name):
    cs=section(name,gap=20e-6,ground_gap=30e-6,top_width=None)
    film=cs.dielectric_regions[0]._shape
    assert film.is_valid and not film.interiors
    sig=[t for t in cs.traces if not t.ground];ground=[t for t in cs.traces if t.ground]
    assert sig[1].x0-sig[0].x1==pytest.approx(20e-6,rel=1e-12)
    assert sig[0].x0-ground[0].x1==pytest.approx(30e-6,rel=1e-12)
    cut=film.intersection(LineString([(-cs.width,sig[0].y+40e-6),(cs.width,sig[0].y+40e-6)]))
    assert cut.geom_type=='LineString'
