# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved bounded strip/grid inputs, material identity and exact field replay."""
from dataclasses import replace
import json
import numpy as np
import pytest
from sipi import StripGridCapacitanceDocument,GridPlateCapacitanceDocument,extract_strip_grid_capacitance
from sipi.capacitance3d_document import Capacitance3DDocument
from sipi.execution import execute_saved,normalize_saved,saved_schemas
import sipi.strip_grid as api
import sipi.strip_grid_document as module


def arguments(**changes):
    a=dict(pitch=1e-3,grid_width=.5e-3,trace_width=.5e-3,height=.5e-3,
        top_clearance=1e-3,backside_depth=1e-3,eps_substrate=3.8,eps_above=1.,eps_below=1.,
        transverse_periods=1,cells_per_pitch=4,cells_substrate=2,cells_above=4,cells_below=4)
    a.update(changes);return a


def document(**changes):return StripGridCapacitanceDocument(**arguments(**changes))
def forbidden(*a,**kw):pytest.fail('validation reached mesh or field work')


def test_canonical_fifteen_keys_and_detached_normalization_without_field(monkeypatch):
    monkeypatch.setattr(api,'box_mesh',forbidden);monkeypatch.setattr(api,'extract_capacitance_3d',forbidden)
    monkeypatch.setattr(module,'extract_strip_grid_capacitance',forbidden)
    a=arguments();d=StripGridCapacitanceDocument(**a);text=d.dumps()
    assert normalize_saved(text)==text and StripGridCapacitanceDocument.loads(text).dumps()==text
    assert 'sipi.strip-grid-capacitance/1' in saved_schemas()
    assert set(d.to_dict())=={'schema','pitch_m','grid_width_m','trace_width_m','height_m',
        'top_clearance_m','backside_depth_m','eps_substrate','eps_above','eps_below',
        'transverse_periods','cells_per_pitch','cells_substrate','cells_above','cells_below'}
    a['eps_above']=99;data=d.to_dict();loaded=StripGridCapacitanceDocument.from_dict(data);data['eps_substrate']=99
    assert loaded.dumps()==text and d.dumps()==text


@pytest.mark.parametrize('key',['schema','pitch_m','grid_width_m','trace_width_m','height_m',
 'top_clearance_m','backside_depth_m','eps_substrate','eps_above','eps_below','transverse_periods',
 'cells_per_pitch','cells_substrate','cells_above','cells_below'])
def test_all_keys_required_before_mesh(key,monkeypatch):
    data=document().to_dict();data.pop(key);monkeypatch.setattr(api,'box_mesh',forbidden)
    with pytest.raises(ValueError):StripGridCapacitanceDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('key,value',[
 ('schema','sipi.strip-grid-capacitance/999'),('schema','sipi.grid-plate-capacitance/1'),('schema',None),
 ('extra',1),('pitch_mm',1.),('grid_width_mm',.5),('trace_width_mm',.5),('height_mm',.5),('frequency_hz',1e9),('thickness_m',1e-6),
 ('pitch_m',0),('grid_width_m',-1),('trace_width_m',False),('height_m',float('inf')),('top_clearance_m',float('nan')),
 ('backside_depth_m',0),('eps_substrate',False),('eps_above',0),('eps_below',-1),
 ('pitch_m',[1e-3]),('grid_width_m',[[.5e-3]]),('eps_substrate',[3.8]),('height_m','0.001'),
 ('grid_width_m',2e-3),('trace_width_m',2e-3),('grid_width_m',.3e-3),('trace_width_m',.3e-3),
 ('grid_width_m',1e-300),('trace_width_m',1e-300),('top_clearance_m',1e-300),
 ('transverse_periods',2),('transverse_periods',11),('transverse_periods',1.),('transverse_periods',True),
 ('cells_per_pitch',3),('cells_per_pitch',5),('cells_per_pitch',34),('cells_per_pitch',4.),
 ('cells_substrate',0),('cells_substrate',129),('cells_substrate',2.),('cells_above',0),('cells_above',129),
 ('cells_below',0),('cells_below',129),('cells_below',False)])
def test_strict_saved_units_geometry_materials_and_counts(key,value,monkeypatch):
    data=document().to_dict();data[key]=value;monkeypatch.setattr(api,'box_mesh',forbidden)
    with pytest.raises((ValueError,TypeError)):StripGridCapacitanceDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('text',['{"schema":"x","schema":"y"}',
 '{"schema":"sipi.strip-grid-capacitance/1","eps_above":NaN}',
 '{"schema":"sipi.strip-grid-capacitance/1","pitch_m":1e999}',
 '{"schema":"sipi.strip-grid-capacitance/1","eps_substrate":3.8,"eps_substrate":4.2}','[]','null'])
def test_duplicate_nonfinite_and_nonobject_reject(text):
    with pytest.raises(ValueError):StripGridCapacitanceDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


@pytest.mark.parametrize('case',['node-budget','tet-budget','small-volume','large-volume'])
def test_physical_budgets_and_volume_checked_during_normalization(case,monkeypatch):
    data=document().to_dict()
    if case=='node-budget':data.update(transverse_periods=9,cells_per_pitch=32,cells_substrate=64,cells_above=64,cells_below=64)
    elif case=='tet-budget':data.update(transverse_periods=3,cells_per_pitch=32,cells_substrate=4,cells_above=12,cells_below=12)
    else:
        factor=1e-150 if case=='small-volume' else 1e150
        for key in ['pitch_m','grid_width_m','trace_width_m','height_m','top_clearance_m','backside_depth_m']:data[key]*=factor
    monkeypatch.setattr(api,'box_mesh',forbidden)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('case',['partial','solid','wide-domain','nonuniform','roundoff'])
def test_direct_saved_and_common_exact_full_field_replay(case):
    a=arguments()
    if case=='solid':a.update(grid_width=1e-3,trace_width=1e-3)
    elif case=='wide-domain':a.update(transverse_periods=3,eps_above=1.3,eps_below=2.1)
    elif case=='nonuniform':a.update(transverse_periods=3,cells_per_pitch=8,grid_width=.25e-3,
        height=.7e-3,top_clearance=.6e-3,backside_depth=1.3e-3,eps_substrate=4.2,eps_above=1.3,eps_below=2.1,
        cells_substrate=3,cells_above=5,cells_below=7)
    elif case=='roundoff':a['grid_width']*=1+2e-13;a['trace_width']*=1-2e-13
    direct=extract_strip_grid_capacitance(**a);d=StripGridCapacitanceDocument(**a)
    replay=StripGridCapacitanceDocument.loads(d.dumps()).analyze(max_evaluations=1)
    assert replay.to_dict(include_fields=True)==direct.to_dict(include_fields=True)
    out=execute_saved(d.dumps(),max_evaluations=2)
    assert out['status']=='complete' and out['error'] is None and out['input']==d.to_dict()
    assert out['result']==direct.to_dict() and not out['result']['fields_included']
    assert not out['result']['cell']['mesh_included'];json.dumps(out,allow_nan=False)
    if case=='roundoff':assert out['result']['cell']['resolved_grid_width_m']!=out['input']['grid_width_m']


def test_one_actual_field_evaluation_and_original_common_budget_minimum(monkeypatch):
    original=module.extract_strip_grid_capacitance;observed=[]
    def spy(**kw):observed.append(kw.copy());return original(**kw)
    monkeypatch.setattr(module,'extract_strip_grid_capacitance',spy);d=document()
    d.analyze(max_evaluations=1);assert observed==[arguments()]
    observed.clear();execute_saved(d.dumps(),max_evaluations=2);assert observed==[arguments()]
    monkeypatch.setattr(module,'extract_strip_grid_capacitance',forbidden)
    with pytest.raises(ValueError):execute_saved(d.dumps(),max_evaluations=1)
    for budget in [0,-1,10001,True,1.,None]:
        with pytest.raises((ValueError,TypeError)):d.analyze(max_evaluations=budget)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])


@pytest.mark.parametrize('change',['type','cell-type','field-type','inputs','grid-edge','trace-edge','grid-width','trace-width',
 'nodes','tets','trace','ground','eps-shape','field-names','field-count','C','energy_C','ground_charge','potentials',
 'tet-index','trace-index','ground-index','nonfinite-node','extent','trace-plane','ground-plane','eps-values','eps-nonfinite'])
def test_saved_result_geometry_material_and_field_identity(change,monkeypatch):
    d=document(eps_substrate=3.8,eps_above=1.3,eps_below=2.1);r=d.analyze()
    if change=='type':bad=None
    elif change=='cell-type':bad=replace(r,cell=None)
    elif change=='field-type':bad=replace(r,field=None)
    elif change=='inputs':
        data=r.inputs;data['eps_substrate']=99;bad=replace(r,cell=replace(r.cell,input_json=json.dumps(data)))
    elif change in ['grid-edge','trace-edge','grid-width','trace-width']:
        name={'grid-edge':'grid_edge_cells','trace-edge':'trace_edge_cells','grid-width':'resolved_grid_width','trace-width':'resolved_trace_width'}[change]
        bad=replace(r,cell=replace(r.cell,**{name:getattr(r.cell,name)*2}))
    elif change in ['nodes','tets','trace','ground','eps-shape']:
        name={'nodes':'nodes','tets':'tets','trace':'trace_nodes','ground':'ground_nodes','eps-shape':'relative_permittivity'}[change]
        bad=replace(r,cell=replace(r.cell,**{name:getattr(r.cell,name)[:-1]}))
    elif change=='field-names':bad=replace(r,field=replace(r.field,names=('other',)))
    elif change=='field-count':bad=replace(r,field=replace(r.field,num_tets=r.field.num_tets+1))
    elif change in ['C','energy_C','ground_charge','potentials']:bad=replace(r,field=replace(r.field,**{change:np.zeros((2,2))}))
    elif change in ['tet-index','trace-index','ground-index','trace-plane','ground-plane']:
        name={'tet-index':'tets','trace-index':'trace_nodes','ground-index':'ground_nodes','trace-plane':'trace_nodes','ground-plane':'ground_nodes'}[change]
        value=getattr(r.cell,name).copy()
        value.flat[0]=len(r.cell.nodes) if 'index' in change else (r.cell.ground_nodes[0] if change=='trace-plane' else r.cell.trace_nodes[0])
        bad=replace(r,cell=replace(r.cell,**{name:value}))
    elif change in ['nonfinite-node','extent']:
        nodes=r.cell.nodes.copy();nodes[0,0]=np.nan if change=='nonfinite-node' else -1.
        bad=replace(r,cell=replace(r.cell,nodes=nodes))
    else:
        eps=r.cell.relative_permittivity.copy();eps[0]=99 if change=='eps-values' else np.nan
        bad=replace(r,cell=replace(r.cell,relative_permittivity=eps))
    monkeypatch.setattr(module,'extract_strip_grid_capacitance',lambda **kw:bad)
    with pytest.raises(ValueError,match='changed saved'):d.analyze()


def test_other_document_kinds_are_not_inferred():
    d=document()
    for cls in [GridPlateCapacitanceDocument,Capacitance3DDocument]:
        with pytest.raises(ValueError):cls.loads(d.dumps())
    for schema in ['sipi.grid-plate-capacitance/1','sipi.capacitance-3d/1','sipi.transmission-line/1','sipi.startup-port-waves/9']:
        data=d.to_dict();data['schema']=schema
        with pytest.raises(ValueError):normalize_saved(json.dumps(data))


def test_original_field_failure_is_retained(monkeypatch):
    def fail(**kw):raise RuntimeError('deliberate saved strip-grid field failure')
    monkeypatch.setattr(module,'extract_strip_grid_capacitance',fail);d=document()
    with pytest.raises(RuntimeError,match='deliberate'):d.analyze()
    with pytest.raises(RuntimeError,match='deliberate'):execute_saved(d.dumps())
