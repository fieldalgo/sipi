# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Material admission and preservation of explicit current evidence."""
from types import SimpleNamespace
import numpy as np
import pytest
from sipi import CrossSection, Layer, Trace, FEMShapeCurrentError
from sipi.templates import coupled_stripline
from sipi.boundary_conductor import SurfaceMetal, LayeredSurfaceMetal
import sipi.fem_shape_loss as api
from test_layered_metal import LAYERS

F = np.array([2e9, 5e9])
OPTIONS = dict(edge_size=5e-6, far_size=.0002, grade=.1)


def geometry(thickness=.00005):
    return coupled_stripline(width=.0004,gap=.0003,plane_spacing=.002,eps_r=4.,thickness=thickness,box_width=.008)


def metals():
    return {'positive':LayeredSurfaceMetal(58e6,coatings=LAYERS),'negative':SurfaceMetal(35e6)}


def arguments():
    return dict(conductors=metals(), reference=SurfaceMetal(58e6),ground_thickness=35e-6,**OPTIONS)


@pytest.mark.parametrize('kind', ['section','missing','extra','metal','reference','dc','frequency','reference-depth','zero-thickness','thin-signal','too-many'])
def test_invalid_input_is_rejected_before_mesh(monkeypatch, kind):
    section=geometry();kw=arguments();frequency=F
    if kind=='section':section=object()
    if kind=='missing':kw['conductors'].pop('positive')
    if kind=='extra':kw['conductors']['unused']=SurfaceMetal(58e6)
    if kind=='metal':kw['conductors']['positive']={}
    if kind=='reference':kw['reference']={}
    if kind=='dc':frequency=[0.,1e9]
    if kind=='frequency':frequency=[np.nan]
    if kind=='reference-depth':kw['ground_thickness']=1e-8
    if kind=='zero-thickness':section=geometry(0.)
    if kind=='thin-signal':section=geometry(1e-6)
    if kind=='too-many':
        section=CrossSection([Layer('vacuum',.002)],[Trace('s'+str(i),(i-2)*.0008,.0004,.0009,.0001) for i in range(5)],.008,top='ground')
        kw['conductors']={t.name:SurfaceMetal(58e6) for t in section.traces}
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid input reached mesh'))
    with pytest.raises((ValueError,TypeError)):api.fem_shape_conductor_loss_by_boundary(section,frequency,**kw)


@pytest.mark.parametrize('which', ['signal','reference'])
def test_coating_core_admission_precedes_mesh(monkeypatch, which):
    kw=arguments();section=geometry(12e-6 if which=='signal' else .00005)
    if which=='reference':kw.update(reference=LayeredSurfaceMetal(58e6,coatings=LAYERS),ground_thickness=12e-6)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid core reached mesh'))
    with pytest.raises(ValueError):api.fem_shape_conductor_loss_by_boundary(section,[1e9],**kw)


def fake_mesh(monkeypatch):
    field=SimpleNamespace(mesh=object(),signals={'positive':np.array([1]),'negative':np.array([2])},ground=np.array([0]));calls=[]
    def meshed(self,**kw):calls.append(kw);return field
    monkeypatch.setattr(CrossSection,'mesh',meshed)
    return field,calls


@pytest.mark.parametrize('error', [RuntimeError('field'),KeyboardInterrupt('cancel'),FEMShapeCurrentError('partial',stage='capacitance-differences',request=(0,0,0,1,1e-9))],ids=['runtime','interrupt','typed-partial'])
def test_current_errors_preserve_identity(monkeypatch,error):
    field,calls=fake_mesh(monkeypatch)
    def fail(mesh,signals,ground):
        assert mesh is field.mesh and signals is field.signals and ground is field.ground
        raise error
    monkeypatch.setattr(api,'fem_shape_current_factors',fail)
    with pytest.raises(type(error)) as caught:api.fem_shape_conductor_loss_by_boundary(geometry(),F,**arguments())
    assert caught.value is error and calls==[OPTIONS]


@pytest.mark.parametrize('kind',['names','flux'])
def test_original_order_and_flux_gates_remain(monkeypatch,kind):
    fake_mesh(monkeypatch)
    factors=SimpleNamespace(names=('negative','positive') if kind=='names' else ('positive','negative'),current_error=.051)
    monkeypatch.setattr(api,'fem_shape_current_factors',lambda *a:factors)
    with pytest.raises(ValueError,match='order' if kind=='names' else 'flux'):
        api.fem_shape_conductor_loss_by_boundary(geometry(),F,**arguments())
