# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed principal axes: constitutive invariants, field references and saved lines."""
import copy
import importlib.metadata as metadata
import json
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.constants import epsilon_0
from galerkin import Mesh
from galerkin.mesh import rectangle_mesh, annulus_mesh
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (CrossSection, CrossSectionDocument, microstrip, coupled_microstrip,
                  NetworkAssemblyDocument, NetworkTransformDocument)
from sipi.dielectric import (ConstantDielectric, DebyeDielectric, WidebandDielectric,
    TabulatedDielectric, PrincipalAxisDielectric, DielectricSweep,
    dielectric_to_dict, dielectric_from_dict, dispersive_line, _dispersive_from_mesh)
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument
from sipi.circuit_document import CircuitDocument
from sipi.termination import terminate_network

F = np.array([1e6, 1e8, 1e10])
MESH = dict(edge_size=10e-6, far_size=.25e-3, grade=.2)


def axes(angle=.4):
    return PrincipalAxisDielectric(DebyeDielectric(2, [3], [1e8]),
                                   WidebandDielectric(4, .02, 1e9), angle)


@pytest.mark.parametrize('angle', [0., np.pi/2, .4, -.7])
def test_principal_eigenvalues_axis_swap_rotation_and_frequency_shapes(angle):
    model = axes(angle)
    q = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    eps = model.permittivity(F)
    assert eps.shape == (3, 2, 2) and model.permittivity(F[0]).shape == (2, 2)
    for i, f in enumerate(F):
        values = [model.axis1.permittivity(f), model.axis2.permittivity(f)]
        np.testing.assert_allclose(q.T@eps[i]@q, np.diag(values), rtol=1e-12, atol=1e-14)
        np.testing.assert_array_equal(eps[i], eps[i].T)
        assert np.linalg.eigvalsh(eps[i].real).min() >= 1
        assert np.linalg.eigvalsh(-eps[i].imag).min() >= 0
    swapped = PrincipalAxisDielectric(model.axis2, model.axis1, angle+np.pi/2)
    np.testing.assert_allclose(swapped.permittivity(F), eps, rtol=1e-12, atol=1e-14)
    np.testing.assert_array_equal(eps[0], model.permittivity(F[0]))


@pytest.mark.parametrize('scalar', [ConstantDielectric(4, .02), DebyeDielectric(2, [2], [1e8]),
    WidebandDielectric(4, .02, 1e9), TabulatedDielectric([1e6, 1e10], [5, 3], [.01, .03])])
def test_all_scalar_models_roundtrip_and_isotropic_limit(scalar):
    old = dielectric_to_dict(scalar)
    assert old['schema'] == 'sipi.dielectric/1'
    model = PrincipalAxisDielectric(scalar, scalar, -.73)
    raw = json.loads(json.dumps(dielectric_to_dict(model), allow_nan=False))
    assert raw['schema'] == 'sipi.dielectric/2' and raw['parameters']['axis1'] == old
    restored = dielectric_from_dict(raw)
    assert restored == model and dielectric_to_dict(restored) == raw
    expected = scalar.permittivity(F)[:, None, None]*np.eye(2)
    np.testing.assert_allclose(restored.permittivity(F), expected, rtol=1e-12, atol=1e-14)
    assert dielectric_to_dict(dielectric_from_dict(old)) == old


@pytest.mark.parametrize('angle', [True, np.bool_(False), '0', None, np.nan, np.inf, 1j, [0.]])
def test_invalid_angle_is_rejected(angle):
    with pytest.raises(ValueError): axes(angle)


@pytest.mark.parametrize('child', [4, {}, object(), axes()])
def test_nested_or_unsupported_axes_are_rejected(child):
    with pytest.raises(ValueError): PrincipalAxisDielectric(child, ConstantDielectric(4))


@pytest.mark.parametrize('mutate', [
    lambda d: d.update(schema='sipi.dielectric/1'),
    lambda d: d.update(kind='constant'),
    lambda d: d.update(kind=[]),
    lambda d: d.update(extra=0),
    lambda d: d['parameters'].update(extra=0),
    lambda d: d['parameters'].pop('angle_rad'),
    lambda d: d['parameters'].update(angle_rad=True),
    lambda d: d['parameters'].update(axis1=dielectric_to_dict(axes())),
    lambda d: d['parameters']['axis2']['parameters'].pop('eps_ref'),
])
def test_versioned_tensor_document_rejects_ambiguous_inputs(mutate):
    raw = dielectric_to_dict(axes()); mutate(raw)
    with pytest.raises(ValueError): dielectric_from_dict(raw)


def test_aligned_layered_frequency_tensor_has_exact_complex_series_capacitance():
    base = rectangle_mesh(.01, .002, 16, 8)
    regions = (base.nodes[base.triangles].mean(axis=1)[:, 1] >= .001).astype(int)
    mesh = Mesh(base.nodes, base.triangles, base.boundary, regions=regions, region_names=['lower','upper'])
    meshed = SimpleNamespace(mesh=mesh, signals={'top':mesh.boundary['top']}, ground=mesh.boundary['bottom'])
    lower = PrincipalAxisDielectric(ConstantDielectric(2), DebyeDielectric(3,[2],[1e8]))
    upper = ConstantDielectric(4,.03)
    samples = {'lower':lower.permittivity(F), 'upper':upper.permittivity(F)}
    result = _dispersive_from_mesh(meshed, F, samples)
    exact = epsilon_0*.01/(.001/lower.axis2.permittivity(F)+.001/upper.permittivity(F))
    np.testing.assert_allclose(result.C_complex[:,0,0], exact, rtol=1e-9, atol=0)
    np.testing.assert_allclose(result.G[:,0,0], -2*np.pi*F*exact.imag, rtol=1e-9, atol=0)
    saved = result.layer_permittivity['lower'].copy()
    samples['lower'][:] = 9
    np.testing.assert_array_equal(result.layer_permittivity['lower'], saved)
    assert result.layer_permittivity['lower'].shape == (3,2,2)
    assert result.layer_permittivity['upper'].shape == (3,)
    assert not result.layer_permittivity['lower'].flags.writeable
    invalid = saved.copy(); invalid[0,0,1] += 1
    with pytest.raises(ValueError, match='symmetric'):
        DielectricSweep(F, result.names, result.C_complex, result.C0, result.L, {'lower':invalid})


def test_dispersive_elliptic_coax_converges_to_exact_transformed_field():
    angle=.4; q=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    root=q@np.diag(np.sqrt([2.,5.]))@q.T
    model=PrincipalAxisDielectric(DebyeDielectric(2,[8],[1e8]), DebyeDielectric(5,[20],[1e8]),angle)
    exact=2*np.pi*epsilon_0*np.sqrt(10)*(1+4/(1+1j*F/1e8))/np.log(3)
    errors=[]
    for nr,nt in ((16,64),(32,128),(64,256)):
        base=annulus_mesh(.5e-3,1.5e-3,nr,nt)
        mesh=Mesh(base.nodes@root.T,base.triangles.copy(),base.boundary,
                  regions=np.zeros(base.num_triangles,int),region_names=['material'])
        meshed=SimpleNamespace(mesh=mesh,signals={'inner':mesh.boundary['inner']},ground=mesh.boundary['outer'])
        result=_dispersive_from_mesh(meshed,F,{'material':model.permittivity(F)})
        errors.append(float(abs(result.C_complex[:,0,0]/exact-1).max()))
    assert errors[2]<errors[1]<errors[0]
    assert errors[-1]<.001 and np.log2(errors[-2]/errors[-1])>=1.5
    print('principal dispersive coax errors',errors)


def test_mixed_scalar_tensor_materials_against_independent_frequency_fem():
    skfem=require_tool('scikit-fem')
    from skfem.helpers import grad
    parameters=dict(width=.5e-3,gap=.3e-3,substrate_height=.5e-3,
        eps_r=4,thickness=35e-6,air_height=4e-3,box_width=8e-3)
    section=coupled_microstrip(**parameters)
    coarse=dict(edge_size=4e-6,far_size=.25e-3,grade=.2)
    fine=dict(edge_size=1e-6,far_size=.125e-3,grade=.1)
    model=axes(); clock=Stopwatch()
    with clock('openphysics'): result=dispersive_line(section,F,materials={'substrate':model},**coarse)
    meshed=section.mesh(**coarse); mesh=meshed.mesh
    basis=skfem.Basis(skfem.MeshTri(mesh.nodes.T,mesh.triangles.T),skfem.ElementTriP1())
    @skfem.BilinearForm(dtype=complex)
    def form(u,v,w): return np.einsum('ij...,j...,i...->...',w.eps,grad(u),grad(v))
    fixed=np.unique(np.concatenate([meshed.ground,*meshed.signals.values()])); errors=[]
    for index,f in enumerate(F):
        eps=np.array([model.permittivity(f) if mesh.region_names[r]=='substrate' else np.eye(2)
                      for r in mesh.regions])
        with clock('reference'):
            k=skfem.asm(form,basis,eps=eps.transpose(1,2,0)[:,:,:,None]); fields=[]
            for nodes in meshed.signals.values():
                v=np.zeros(basis.N,complex); v[nodes]=1
                fields.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,complex),x=v,D=fixed)))
            u=np.array(fields).T; expected=epsilon_0*(u.T@(k@u))
        errors.append(float(abs(result.C_complex[index]/expected-1).max()))
    error=max(errors)
    record=make_record(case='principal-dispersive-coupled-line',physics='reciprocal transverse dispersive dielectric',
        api='sipi.dielectric.dispersive_line',discretization='principal-axis models on shared P1 mesh',
        tool='scikit-fem',tool_discretization='independent complex tensor P1 assembly and field energy',
        matched=['same mesh, boundaries and complex tensor samples at three frequencies'],
        not_matched=['same-mesh agreement is not mesh convergence or measured material validation'],
        observables=[observable('complex C','F/m','max relative difference',error,1e-9)],
        analytical_acceptance='layered series capacitor and dispersive transformed elliptic coax mesh convergence',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi')); emit(record)
    assert error<1e-9
    refined=dispersive_line(section,F,materials={'substrate':model},**fine)
    outer_section=coupled_microstrip(**dict(parameters,air_height=8e-3,box_width=16e-3))
    outer=dispersive_line(outer_section,F,materials={'substrate':model},**fine)
    mesh_change=float(abs(result.C_complex/refined.C_complex-1).max())
    outer_change=float(abs(outer.C_complex/refined.C_complex-1).max())
    assert mesh_change<.01 and outer_change<.01
    print('principal material mesh/outer changes',mesh_change,outer_change)
    net=result.network(length=.01,R=np.zeros((2,2)))
    np.testing.assert_allclose(net.s,net.s.swapaxes(-1,-2),rtol=0,atol=1e-10)
    assert np.linalg.svd(net.s,compute_uv=False).max()<=1+1e-10


def line_document(material, conductor=None, frequency=F):
    section=microstrip(width=.4e-3,substrate_height=.5e-3,thickness=.1e-3,
                      eps_r=4,air_height=.5e-3,box_width=2e-3)
    mesh = (dict(edge_size=2e-6,far_size=.125e-3,grade=.1)
            if conductor and conductor['kind']=='surface' else MESH)
    return TransmissionLineDocument(CrossSectionDocument(section,mesh=mesh),frequency,
        materials={'substrate':material},conductor=conductor or {'kind':'perfect'},length=.01)


@pytest.mark.parametrize('conductor', [{'kind':'perfect'},dict(kind='surface',conductivity=58e6,
    ground_thickness=100e-6,relative_permeability=1,roughness_rms=0)])
def test_saved_line_isotropic_tensor_matches_scalar_and_builds_one_mesh(conductor,monkeypatch):
    # The surface approximation needs skin depth <= one fifth of metal thickness.
    frequency=[1e8,1e9,1e10]
    scalar=DebyeDielectric(2,[2],[1e8]); reference=line_document(scalar,conductor,frequency).analyze()
    calls=[]; original=CrossSection.mesh
    def counted(*args,**kwargs): calls.append(1); return original(*args,**kwargs)
    monkeypatch.setattr(CrossSection,'mesh',counted)
    document=line_document(PrincipalAxisDielectric(scalar,scalar,.4),conductor,frequency)
    restored=TransmissionLineDocument.loads(document.dumps()); assert not calls
    actual=restored.analyze(); assert len(calls)==1 and actual.input_json==document.dumps()
    for name in ('R','L','G','C'):
        np.testing.assert_allclose(getattr(actual,name),getattr(reference,name),rtol=1e-12,atol=0)
    np.testing.assert_allclose(actual.network.s,reference.network.s,rtol=0,atol=1e-10)


def test_nested_table_range_and_unknown_materials_fail_before_geometry(monkeypatch):
    def forbidden(*args,**kwargs): pytest.fail('invalid tensor request reached geometry')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    table=PrincipalAxisDielectric(TabulatedDielectric([1e8,1e9],[4,3],[.01,.02]),ConstantDielectric(4))
    with pytest.raises(ValueError,match='extrapolation'): line_document(table)
    raw=line_document(axes()).to_dict(); raw['materials']['unknown']=raw['materials']['substrate']
    with pytest.raises(ValueError,match='unknown'): TransmissionLineDocument.from_dict(raw)
    raw=line_document(axes()).to_dict(); raw['materials']['substrate']['parameters']['angle_rad']=True
    with pytest.raises(ValueError): TransmissionLineDocument.from_dict(raw)


@pytest.mark.parametrize('kind',['transmission-line','volume-line'])
def test_anisotropic_saved_line_assembly_transform_and_driven_circuit(kind,monkeypatch):
    inner=line_document(axes(),frequency=[1e3,1e5])
    if kind=='volume-line':
        inner=VolumeLineDocument(CrossSectionDocument(inner.cross_section.section),[1e3,1e5],
            materials={'substrate':axes()},conductivity=58e6,length=.01,
            mesh=dict(ground_thickness=.1e-3,padding=2e-3,metal_size=50e-6,
                      far_size=.5e-3,grade=.2,min_angle=28))
    direct=inner.analyze(); calls=[]; original=type(inner).analyze
    def counted(*args,**kwargs): calls.append(1); return original(*args,**kwargs)
    monkeypatch.setattr(type(inner),'analyze',counted)
    start=dict(kind='ideal-junction',frequency_hz=[1e3,1e5],port_names=['input','join'],reference_ohms=50)
    assembled=NetworkAssemblyDocument(start,connections=[dict(
        network=dict(kind=kind,document=inner.to_dict()),ports=[['join','near:signal']])])
    transformed=NetworkTransformDocument(dict(kind='network-assembly',document=assembled.to_dict()),
        operations=[dict(kind='renormalize',reference_ohms=[75,100])])
    circuit=CircuitDocument(dict(kind='network-transform',document=transformed.to_dict()),
        excitation=dict(kind='sources',voltages={'input':1}),terminations={'input':50,'far:signal':100})
    restored=CircuitDocument.loads(circuit.dumps()); assert not calls
    out=restored.analyze(); assert len(calls)==1
    expected=terminate_network(direct.network,source_voltages={'near:signal':1},
                               terminations={'near:signal':50,'far:signal':100})
    np.testing.assert_allclose(out.response.voltage,expected.voltage,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(out.response.current,expected.current,rtol=1e-10,atol=1e-12)
    extracted=out.extraction.extraction.extractions[1]
    assert extracted.input_json==inner.dumps()
    if kind=='volume-line':
        raw=copy.deepcopy(inner.to_dict())
        raw['materials']['substrate']=dielectric_to_dict(ConstantDielectric(4))
        isotropic=VolumeLineDocument.from_dict(raw).analyze()
        for name in ('R','L'): np.testing.assert_array_equal(getattr(extracted,name),getattr(isotropic,name))
        assert not np.allclose(extracted.C,isotropic.C,rtol=1e-3,atol=0)


def test_volume_isotropic_tensor_preserves_all_scalar_rlgc_and_network():
    section=line_document(axes()).cross_section.section
    scalar=DebyeDielectric(2,[2],[1e4])
    doc=VolumeLineDocument(CrossSectionDocument(section),[0,1e3,1e5],
        materials={'substrate':scalar},conductivity=58e6,length=.01,
        mesh=dict(ground_thickness=.1e-3,padding=2e-3,metal_size=50e-6,
                  far_size=.5e-3,grade=.2,min_angle=28))
    reference=doc.analyze(); raw=doc.to_dict()
    raw['materials']['substrate']=dielectric_to_dict(PrincipalAxisDielectric(scalar,scalar,-.7))
    tensor=VolumeLineDocument.from_dict(raw).analyze()
    for name in ('R','L','G','C'):
        np.testing.assert_allclose(getattr(tensor,name),getattr(reference,name),rtol=1e-12,atol=0)
    np.testing.assert_allclose(tensor.network.s,reference.network.s,rtol=0,atol=1e-10)
