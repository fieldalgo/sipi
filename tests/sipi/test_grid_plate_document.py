# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict bounded static inputs, pre-mesh validation and full-field replay."""
from dataclasses import replace
import json
import numpy as np
import pytest
from sipi import GridPlateCapacitanceDocument, extract_grid_plate_capacitance
from sipi.capacitance3d_document import Capacitance3DDocument
from sipi.execution import execute_saved,normalize_saved,saved_schemas
import sipi.grid_plate as api
import sipi.grid_plate_document as module


def arguments(**changes):
    a=dict(pitch=1e-3,width=.5e-3,height=.5e-3,backside_depth=1e-3,eps_r=3.8,
        cells_xy=4,cells_above=2,cells_below=4);a.update(changes);return a


def document(**changes):return GridPlateCapacitanceDocument(**arguments(**changes))


def forbidden(*a,**kw):pytest.fail('validation or budget reached mesh/field work')


def test_canonical_nine_keys_and_copies_without_mesh_or_field(monkeypatch):
    monkeypatch.setattr(api,'box_mesh',forbidden);monkeypatch.setattr(api,'extract_capacitance_3d',forbidden)
    monkeypatch.setattr(module,'extract_grid_plate_capacitance',forbidden)
    args=arguments();d=GridPlateCapacitanceDocument(**args);text=d.dumps()
    assert normalize_saved(text)==text and GridPlateCapacitanceDocument.loads(text).dumps()==text
    assert 'sipi.grid-plate-capacitance/1' in saved_schemas()
    assert set(d.to_dict())=={'schema','pitch_m','width_m','height_m','backside_depth_m','eps_r','cells_xy','cells_above','cells_below'}
    args['width']=9;data=d.to_dict();loaded=GridPlateCapacitanceDocument.from_dict(data);data['width_m']=9
    assert loaded.dumps()==text and d.dumps()==text


@pytest.mark.parametrize('key',['schema','pitch_m','width_m','height_m','backside_depth_m','eps_r','cells_xy','cells_above','cells_below'])
def test_all_keys_required_before_mesh(key,monkeypatch):
    data=document().to_dict();data.pop(key);monkeypatch.setattr(api,'box_mesh',forbidden)
    with pytest.raises(ValueError):GridPlateCapacitanceDocument.from_dict(data)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('key,value',[
    ('schema','sipi.grid-plate-capacitance/2'),('schema','sipi.capacitance-3d/1'),('schema',None),
    ('extra',1),('pitch_mm',1.),('width_mm',.5),('height_mm',.5),('frequency_hz',1e9),('thickness_m',1e-6),
    ('pitch_m',0),('width_m',-1),('height_m',False),('backside_depth_m',float('inf')),('eps_r',float('nan')),
    ('pitch_m',[1e-3]),('width_m',[[.5e-3]]),('eps_r',[3.8]),('height_m','0.001'),
    ('width_m',2e-3),('width_m',.3e-3),('width_m',1e-300),
    ('cells_xy',3),('cells_xy',5),('cells_xy',66),('cells_xy',4.),('cells_xy',True),
    ('cells_above',0),('cells_above',65),('cells_above',2.),('cells_below',0),('cells_below',129),('cells_below',False)])
def test_strict_saved_geometry_and_units_before_mesh(key,value,monkeypatch):
    data=document().to_dict();data[key]=value;monkeypatch.setattr(api,'box_mesh',forbidden)
    with pytest.raises((ValueError,TypeError)):GridPlateCapacitanceDocument.from_dict(data)
    with pytest.raises((ValueError,TypeError)):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('text',['{"schema":"x","schema":"y"}',
    '{"schema":"sipi.grid-plate-capacitance/1","eps_r":NaN}',
    '{"schema":"sipi.grid-plate-capacitance/1","pitch_m":1e999}',
    '{"schema":"sipi.grid-plate-capacitance/1","eps_r":3.8,"eps_r":4.2}','[]','null'])
def test_duplicate_nonfinite_and_nonobject_reject(text):
    with pytest.raises(ValueError):GridPlateCapacitanceDocument.loads(text)
    with pytest.raises(ValueError):normalize_saved(text)


@pytest.mark.parametrize('case',['too-many-nodes','small-volume','large-volume'])
def test_physical_mesh_budget_and_volume_checked_during_normalization(case,monkeypatch):
    data=document().to_dict()
    if case=='too-many-nodes':data.update(cells_xy=64,cells_above=32,cells_below=64)
    else:
        factor=1e-150 if case=='small-volume' else 1e150
        for key in ['pitch_m','width_m','height_m','backside_depth_m']:data[key]*=factor
    monkeypatch.setattr(api,'box_mesh',forbidden)
    with pytest.raises(ValueError):normalize_saved(json.dumps(data))


@pytest.mark.parametrize('case',['partial','solid','nonuniform','roundoff'])
def test_direct_saved_and_common_exact_full_field_replay(case):
    a=arguments()
    if case=='solid':a['width']=a['pitch']
    elif case=='nonuniform':a.update(cells_xy=8,width=.25e-3,height=.7e-3,backside_depth=1.3e-3,cells_above=3,cells_below=5)
    elif case=='roundoff':a['width']*=1+2e-13
    direct=extract_grid_plate_capacitance(**a);d=GridPlateCapacitanceDocument(**a)
    replay=GridPlateCapacitanceDocument.loads(d.dumps()).analyze(max_evaluations=1)
    assert replay.to_dict(include_fields=True)==direct.to_dict(include_fields=True)
    out=execute_saved(d.dumps(),max_evaluations=2)
    assert out['status']=='complete' and out['error'] is None and out['input']==d.to_dict()
    assert out['result']==direct.to_dict() and not out['result']['fields_included']
    assert not out['result']['cell']['mesh_included'];json.dumps(out,allow_nan=False)
    if case=='roundoff':assert out['result']['cell']['resolved_width_m']!=out['input']['width_m']


def test_one_field_evaluation_and_unchanged_common_budget_minimum(monkeypatch):
    original=module.extract_grid_plate_capacitance;observed=[]
    def spy(**kw):observed.append(kw.copy());return original(**kw)
    monkeypatch.setattr(module,'extract_grid_plate_capacitance',spy);d=document()
    d.analyze(max_evaluations=1);assert observed==[arguments()]
    observed.clear();execute_saved(d.dumps(),max_evaluations=2);assert observed==[arguments()]
    monkeypatch.setattr(module,'extract_grid_plate_capacitance',forbidden)
    # Common execution retains its pre-existing integer2..10000 budget contract.
    with pytest.raises(ValueError):execute_saved(d.dumps(),max_evaluations=1)
    for budget in [0,-1,10001,True,1.,None]:
        with pytest.raises((ValueError,TypeError)):d.analyze(max_evaluations=budget)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(d.dumps(),max_input_bytes=2)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(d.dumps(),diagnostics=['modes'])


@pytest.mark.parametrize('change',['type','cell-type','field-type','inputs','edge','width','nodes','tets','plate','ground','field-names','field-count','C','energy_C','ground_charge','potentials'])
def test_saved_result_identity_and_geometry_field_shapes(change,monkeypatch):
    d=document();r=d.analyze()
    if change=='type':bad=None
    elif change=='cell-type':bad=replace(r,cell=None)
    elif change=='field-type':bad=replace(r,field=None)
    elif change=='inputs':
        data=r.inputs;data['height_m']*=2;bad=replace(r,cell=replace(r.cell,input_json=json.dumps(data)))
    elif change=='edge':bad=replace(r,cell=replace(r.cell,edge_cells=r.cell.edge_cells+1))
    elif change=='width':bad=replace(r,cell=replace(r.cell,resolved_width=r.cell.resolved_width*2))
    elif change in ['nodes','tets','plate','ground']:
        field={'nodes':'nodes','tets':'tets','plate':'plate_nodes','ground':'ground_nodes'}[change]
        value=getattr(r.cell,field)[:-1];bad=replace(r,cell=replace(r.cell,**{field:value}))
    elif change=='field-names':bad=replace(r,field=replace(r.field,names=('other',)))
    elif change=='field-count':bad=replace(r,field=replace(r.field,num_tets=r.field.num_tets+1))
    else:bad=replace(r,field=replace(r.field,**{change:np.zeros((2,2))}))
    monkeypatch.setattr(module,'extract_grid_plate_capacitance',lambda **kw:bad)
    with pytest.raises(ValueError,match='changed saved'):d.analyze()


def test_other_input_kinds_are_not_inferred():
    d=document()
    with pytest.raises(ValueError):Capacitance3DDocument.loads(d.dumps())
    for schema in ['sipi.capacitance-3d/1','sipi.transmission-line/1','sipi.startup-port-waves/9']:
        data=d.to_dict();data['schema']=schema
        with pytest.raises(ValueError):normalize_saved(json.dumps(data))


def test_original_field_failure_is_retained(monkeypatch):
    d=document()
    def fail(**kw):raise RuntimeError('deliberate saved static field failure')
    monkeypatch.setattr(module,'extract_grid_plate_capacitance',fail)
    with pytest.raises(RuntimeError,match='deliberate'):d.analyze()
    with pytest.raises(RuntimeError,match='deliberate'):execute_saved(d.dumps())
