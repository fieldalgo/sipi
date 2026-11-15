# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
from types import SimpleNamespace
import numpy as np
import pytest
from scipy.linalg import expm
from sipi import CrossSection,CrossSectionDocument,Layer
from sipi.constants import epsilon_0,mu_0
from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument as Document,TwoGroundPanelLineError
import sipi.two_ground_panel_line as module
import sipi.two_ground_conductor as current
from test_two_ground_conductor import ROWS,section,F
from test_layered_metal import transfer


def metal(sigma):return dict(conductivity=sigma,relative_permeability=1.,roughness={"kind":"smooth"})


def document(case="scalar-offset",distinct=False,panels=64):
    row=next(x for x in ROWS if x["case"]==case);sec=section(row)
    sec=CrossSection([Layer("uniform",row["height"],4.,tan_delta=.003)],sec.traces,sec.width,top="ground")
    coated=dict(kind="layered",conductivity=58e6,relative_permeability=1.,coatings=[
        dict(thickness_m=2e-7,conductivity=14e6,relative_permeability=3.),
        dict(thickness_m=1e-6,conductivity=40e6,relative_permeability=1.)])
    return Document(CrossSectionDocument(sec,mesh=dict(edge_size=5e-6,far_size=.0001,grade=.05)),
        F,materials={},conductors={t.name:coated if t.name=="positive" else metal(35e6) for t in sec.traces},
        reference=dict(kind="surfaces",bottom=metal(58e6),top=metal(21e6 if distinct else 58e6),sides=None,conductors={}),
        ground_thickness=35e-6,length=.02,panels_per_edge=panels,interpolation_degree=row["degree"])


def test_field_free_detached_roundtrip_without_shared_capability(monkeypatch):
    def forbidden(*a,**k):pytest.fail("normalization reached fields")
    monkeypatch.setattr(current,"_solver",forbidden);monkeypatch.setattr(CrossSection,"mesh",forbidden)
    doc=document();text=doc.dumps();assert Document.loads(text).dumps()==text
    raw=doc.to_dict();raw["reference"]["top"]["conductivity"]=1
    doc.current_options["ground_modes"]=64
    assert doc.dumps()==text and doc.cross_section.to_dict()==doc.to_dict()["cross_section"]


@pytest.mark.parametrize("where",["root","panel","section","signal","reference","top","coating"])
@pytest.mark.parametrize("change",["extra","missing"])
def test_strict_nested_keys(where,change):
    raw=document().to_dict();target={"root":raw,"panel":raw["panel"],"section":raw["cross_section"],
        "signal":raw["conductors"]["positive"],"reference":raw["reference"],"top":raw["reference"]["top"],
        "coating":raw["conductors"]["positive"]["coatings"][0]}[where]
    if change=="extra":target["unexpected"]=1
    else:target.pop(next(iter(target)))
    with pytest.raises((ValueError,TypeError)):Document.from_dict(raw)


@pytest.mark.parametrize("case",["unknown-schema","duplicate","nonfinite","bad-panel","bad-degree","bad-modes",
    "missing-top","side-metal","signal-name","dc","length","zref","skin","core","material-name","wall","zero-thickness"])
def test_invalid_saved_input_before_fields(monkeypatch,case):
    def forbidden(*a,**k):pytest.fail("invalid input reached fields")
    monkeypatch.setattr(current,"_solver",forbidden);monkeypatch.setattr(CrossSection,"mesh",forbidden)
    raw=document().to_dict()
    if case=="unknown-schema":raw["schema"]+="-unknown"
    if case=="bad-panel":raw["panel"]["panels_per_edge"]=False
    if case=="bad-degree":raw["panel"]["interpolation_degree"]=11
    if case=="bad-modes":raw["panel"]["ground_modes"]=63
    if case=="missing-top":raw["reference"]["top"]=None
    if case=="side-metal":raw["reference"]["sides"]=metal(58e6)
    if case=="signal-name":raw["conductors"]["extra"]=metal(58e6)
    if case=="dc":raw["frequency_hz"][0]=0
    if case=="length":raw["length_m"]=-1
    if case=="zref":raw["reference_ohms"]=0
    if case=="skin":raw["ground_thickness_m"]=1e-7
    if case=="core":raw["conductors"]["positive"]["coatings"][0]["thickness_m"]=.001
    if case=="material-name":raw["materials"]={"missing":{"kind":"constant","epsilon_r":4.,"tan_delta":0.}}
    if case=="wall":raw["cross_section"]["box"]["top"]="open"
    if case=="zero-thickness":
        for vertex in raw["cross_section"]["traces"][0]["vertices"]:vertex[1]=.0007
    text=json.dumps(raw)
    if case=="duplicate":text=text.replace('"length_m": 0.02','"length_m": 0.02, "length_m": 0.02')
    if case=="nonfinite":text=text.replace('"length_m": 0.02','"length_m": NaN')
    with pytest.raises((ValueError,TypeError)):Document.loads(text)


@pytest.fixture(scope="module")
def observed():
    return [(document(case,distinct),document(case,distinct).analyze())
        for case in ("scalar-offset","box-8","pair-asymmetric") for distinct in (False,True)]


def independent_network(f,R,L,G,C,length,zref):
    n=len(R);z=R+2j*np.pi*f*L;y=G+2j*np.pi*f*C
    transfer_matrix=expm(length*np.block([[np.zeros((n,n)),z],[y,np.zeros((n,n))]]))
    # Convert the independent V/I propagation relation directly to port waves.
    a,b,c,d=transfer_matrix[:n,:n],transfer_matrix[:n,n:],transfer_matrix[n:,:n],transfer_matrix[n:,n:]
    left=np.block([[np.eye(n),-a-b/zref],[-np.eye(n),-zref*c-d]])
    right=np.block([[-np.eye(n),a-b/zref],[-np.eye(n),zref*c-d]])
    return np.linalg.solve(left,right)


def test_actual_six_lines_independent_uniform_and_network_invariants(observed,record_property):
    records=[]
    for doc,result in observed:
        data=doc.to_dict();f=result.frequency;factors=result.current_factors;n=len(result.names)
        np.testing.assert_allclose(result.C,4*np.broadcast_to(factors.C0,result.C.shape),rtol=1e-12,atol=0)
        np.testing.assert_allclose(result.G,2*np.pi*f[:,None,None]*.003*result.C,rtol=1e-12,atol=0)
        np.testing.assert_allclose(result.dielectric.L@factors.C0,mu_0*epsilon_0*np.eye(n),rtol=1e-10,atol=1e-28)
        zs=[]
        for name in result.conductor.boundary_labels:
            if name=="signal:positive":zs.append(np.array([transfer(x) for x in f]))
            else:
                sigma=35e6 if name=="signal:negative" else data["reference"][name.split(":")[1]]["conductivity"]
                zs.append(np.sqrt(2j*np.pi*f*mu_0/sigma))
        power=sum(z[:,None,None]*q for z,q in zip(zs,factors.boundary_parts))
        np.testing.assert_allclose(result.R,power.real,rtol=1e-12,atol=0)
        np.testing.assert_allclose(result.conductor.L_internal,power.imag/(2*np.pi*f[:,None,None]),rtol=1e-12,atol=0)
        for i,x in enumerate(f):
            reference=independent_network(x,result.R[i],result.L[i],result.G[i],result.C[i],.02,50.)
            np.testing.assert_allclose(result.network.s[i],reference,rtol=1e-10,atol=1e-12)
        assert result.input_json==doc.dumps() and result.current_record()["kind"]=="two-ground-rectangle-panels"
        assert result.mesh_record()["nodes"]>0
        for prop in (result.current_record(),result.mesh_record()):prop.clear()
        assert result.current_record() and result.mesh_record()
        records.append(dict(input=data,current=result.current_record(),mesh=result.mesh_record(),R=result.R.tolist(),
            L=result.L.tolist(),G=result.G.tolist(),C=result.C.tolist(),s_real=result.network.s.real.tolist(),s_imag=result.network.s.imag.tolist()))
    record_property("two_ground_lines",json.dumps(records,sort_keys=True))


@pytest.mark.parametrize("stage",["current","mesh","dielectric","network"])
def test_staged_failure_retains_completed_current(monkeypatch,observed,stage):
    doc,result=observed[0];original=module.two_ground_conductor_loss
    def failure(*a,**k):raise ArithmeticError("controlled stage failure")
    monkeypatch.setattr(module,"two_ground_conductor_loss",lambda *a,**k:result.conductor)
    if stage=="current":monkeypatch.setattr(module,"two_ground_conductor_loss",failure)
    if stage=="mesh":monkeypatch.setattr(CrossSection,"mesh",failure)
    if stage=="dielectric":monkeypatch.setattr(module,"_dispersive_from_mesh",failure)
    if stage=="network":monkeypatch.setattr(module,"rlgc_network",failure)
    with pytest.raises(TwoGroundPanelLineError) as info:doc.analyze()
    error=info.value;record=error.to_dict()
    assert error.stage==stage and error.cause_type=="ArithmeticError" and error.input_json==doc.dumps()
    assert record["input"]==doc.to_dict()
    assert (record["current_solver"] is None)==(stage=="current")
    assert (record["dielectric_mesh"] is None)==(stage in ("current","mesh"))
    if stage!="current":assert record["current_solver"]==result.current_record()
    record.clear();assert error.to_dict()


def test_actual_missing_shared_capability_has_typed_current_failure(monkeypatch):
    def missing(*a,**k):raise RuntimeError("absent optional capability")
    monkeypatch.setattr(current,"_solver",missing)
    with pytest.raises(TwoGroundPanelLineError) as info:document().analyze()
    assert info.value.stage=="current" and info.value.cause_type=="RuntimeError"
    assert info.value.to_dict()["current_solver"] is None


def test_layered_dielectric_refinement_and_independent_complex_p2(record_property):
    import skfem as sk
    from skfem.helpers import dot, grad
    raw=document().to_dict()
    raw['cross_section']['layers']=[dict(name='lower',thickness=.001,eps_r=3.,tan_delta=.002),
                                    dict(name='upper',thickness=.001,eps_r=5.,tan_delta=.004)]
    rows=[];docs=[]
    for edge,far,grade in [(1e-5,.00015,.075),(5e-6,.0001,.05),(2.5e-6,.000075,.0375)]:
        raw['cross_section']['mesh'].update(edge_size=edge,far_size=far,grade=grade)
        doc=Document.from_dict(raw);docs.append(doc);rows.append(doc.analyze())
    changes=[]
    for a,b in zip(rows,rows[1:]):
        item={key:float(np.max(abs(getattr(a,key)-getattr(b,key))/np.maximum(abs(getattr(a,key)),abs(getattr(b,key))))) for key in ('C','G')}
        changes.append(item);assert max(item.values())<=.01
    doc=docs[-1];result=rows[-1];field=doc.cross_section.section.mesh(**doc.cross_section.mesh_options)
    assert module._mesh_record(field)==result.mesh_record()
    m=sk.MeshTri(field.mesh.nodes.T.copy(),field.mesh.triangles.T.copy())
    basis=sk.Basis(m,sk.ElementTriP2(),intorder=4)
    facets=m.boundary_facets();nodes=m.facets[:,facets]
    signals=next(iter(field.signals.values()))
    signal_facets=facets[np.all(np.isin(nodes,signals),axis=0)]
    ground_facets=facets[np.all(np.isin(nodes,field.ground),axis=0)]
    signal=basis.get_dofs(facets=signal_facets).all();ground=basis.get_dofs(facets=ground_facets).all()
    assert len(signal)>len(signals) and len(ground)>len(field.ground)
    centers=m.p[:,m.t].mean(axis=1)
    eps=np.where(centers[1]<.001,3*(1-.002j),5*(1-.004j))
    @sk.BilinearForm(dtype=complex)
    def form(u,v,w):return w.eps*dot(grad(u),grad(v))
    k=form.assemble(basis,eps=eps[:,None]);v=np.zeros(basis.N,dtype=complex);v[signal]=1
    v=sk.solve(*sk.condense(k,np.zeros(basis.N,dtype=complex),x=v,D=np.unique(np.r_[signal,ground])))
    reaction=k@v;cap=epsilon_0*np.sum(reaction[signal]);energy=epsilon_0*(v@(k@v))
    assert abs(cap-energy)/abs(cap)<=1e-10
    assert abs(np.sum(reaction[signal])+np.sum(reaction[ground]))/abs(np.sum(reaction[signal]))<=1e-10
    reference_c=np.full_like(result.C,cap.real)
    reference_g=np.broadcast_to((-2*np.pi*result.frequency*cap.imag)[:,None,None],result.G.shape)
    np.testing.assert_allclose(result.C,reference_c,rtol=.01,atol=0)
    np.testing.assert_allclose(result.G,reference_g,rtol=.01,atol=0)
    # A nonuniform solve must not take the homogeneous scaling shortcut.
    assert not np.allclose(result.C,4*np.broadcast_to(result.current_factors.C0,result.C.shape),rtol=.01,atol=0)
    record_property('two_ground_layered_dielectric',json.dumps(dict(
        inputs=[d.to_dict() for d in docs],changes=changes,
        C=[x.C.tolist() for x in rows],G=[x.G.tolist() for x in rows],
        mesh=[x.mesh_record() for x in rows],reference_C=reference_c.tolist(),reference_G=reference_g.tolist(),
        reference_dofs=int(basis.N),reference='independent complex P2 boundary reactions'),sort_keys=True))
