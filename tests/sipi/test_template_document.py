# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Editable template snapshots, prior geometry and independent stripline checks."""
from dataclasses import FrozenInstanceError
from functools import wraps
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.constants import epsilon_0, mu_0
from scipy.special import ellipk, ellipkm1

from sipi import CrossSection, CrossSectionDocument
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from sipi.study import _TEMPLATES
from sipi.template_document import TemplateSectionDocument as Template

REFERENCE = json.loads((Path(__file__).parent/'reference_data/template_section/reference.json').read_text())
CASES = {row['template']: row for row in REFERENCE['cases']}
MESH = dict(edge_size=40e-6, far_size=.25e-3, grade=.3)
PARAMS = dict(width=.5e-3, plane_spacing=1e-3, eps_r=4.)


def stripline(**parameters):
    return Template('stripline', dict(PARAMS, **parameters), mesh=MESH)


@pytest.mark.parametrize('name', sorted(CASES))
def test_every_existing_template_matches_frozen_geometry_and_resolved_inputs(name, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('template preparation performed meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    row = CASES[name]
    doc = Template(name, row['supplied_parameters'])
    assert doc.parameters == row['resolved_parameters']
    assert doc.cross_section.to_dict() == row['cross_section']
    assert hashlib.sha256(doc.cross_section.dumps().encode()).hexdigest() == row['cross_section_sha256']
    assert Template.loads(doc.dumps()).dumps() == doc.dumps()
    assert doc.template == name
    assert set(doc.mesh_options) == {'edge_size', 'far_size', 'grade', 'min_angle'}


def test_reference_preserves_exact42_original_factories_and_surface_extensions():
    assert set(CASES) | {'layered_microstrip', 'coupled_layered_microstrip', 'asymmetric_coupled_layered_microstrip',
                         'layered_grounded_coplanar', 'coupled_layered_grounded_coplanar',
                         'asymmetric_coupled_layered_grounded_coplanar',
                         'layered_unbacked_coplanar', 'coupled_layered_unbacked_coplanar',
                         'asymmetric_coupled_layered_unbacked_coplanar'} == set(_TEMPLATES)
    assert len(CASES) == 42
    assert REFERENCE['engine_commit'] == '4445d5ce3a0e9e186e33fb8d12354a2339f6e0df'


@pytest.mark.parametrize('name', ['stripline', 'coupled_microstrip',
    'asymmetric_coupled_conformal_coated_unbacked_coplanar'])
def test_actual_analysis_and_shared_execution_preserve_direct_matrices(name):
    params = CASES[name]['supplied_parameters']
    wrapped = Template(name, params, mesh=MESH)
    original = CrossSectionDocument(_TEMPLATES[name](**wrapped.parameters), mesh=wrapped.mesh_options)
    direct = original.analyze()
    actual = wrapped.analyze()
    output = execute_saved(wrapped.dumps())
    assert output['status'] == 'complete' and output['error'] is None
    assert output['input'] == wrapped.to_dict() and output['result']['names'] == list(direct.names)
    for key, field in [('C_f_per_m', 'C'), ('C0_f_per_m', 'C0'), ('C_loss_f_per_m', 'C_loss'), ('L_h_per_m', 'L')]:
        np.testing.assert_array_equal(getattr(actual, field), getattr(direct, field))
        np.testing.assert_array_equal(output['result'][key], getattr(direct, field))
    if len(direct.names) == 1:
        assert output['result']['z0_ohm'] == direct.z0


def test_independent_cohn_mesh_and_outer_domain_contract(record_property):
    # Independent zero-thickness conformal map; no template/helper reference calls.
    w, b, er = .5e-3, 1e-3, 4.
    k = 1 / np.cosh(np.pi*w/(2*b))
    exact = np.sqrt(mu_0/epsilon_0) / (4*np.sqrt(er)) * ellipk(k*k)/ellipkm1(k*k)
    values = []
    for s in (1, 2, 4):
        mesh = dict(edge_size=8e-6/s**2, grade=.3/s, far_size=b/(4*s))
        doc = Template('stripline', dict(width=w, plane_spacing=b, eps_r=er, box_width=12*b), mesh=mesh)
        line = doc.analyze()
        assert line.eps_eff == pytest.approx(er, rel=1e-12)
        values.append(line.z0)
    errors = np.abs(np.asarray(values)/exact-1)
    assert errors[-1] <= .005 and errors[0] > errors[1] > errors[2]
    outer = Template('stripline', dict(width=w, plane_spacing=b, eps_r=er, box_width=16*b), mesh=mesh).analyze().z0
    change = abs(outer/values[-1]-1)
    assert change <= .001
    record_property('independent_cohn', json.dumps(dict(exact_ohm=exact, values_ohm=values,
        relative_errors=errors.tolist(), outer_ohm=outer, outer_relative_change=change)))


def test_saved_request_record_project_reopen_and_edit_invalidation(monkeypatch):
    doc = stripline()
    request = SavedExecutionRequest(doc.dumps())
    receipt = request.run()
    record = SavedExecutionRecord(request, receipt, run_id='template:1', artifacts=[
        dict(component='sipi', version='example-only', kind='wheel', sha256='1'*64)])
    project = SavedProject(request, project_id='p', design_id='a', title='Design', label='A')
    project = project.attach_record('a', record, select=True)
    def forbidden(*args, **kwargs):
        pytest.fail('reopening or editing performed a calculation')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(SavedExecutionRequest, 'run', forbidden)
    reopened = SavedProject.loads(project.dumps())
    recovered = Template.loads(reopened.prepare('a').source_text)
    assert recovered.parameters == doc.parameters and recovered.cross_section.dumps() == doc.cross_section.dumps()
    edited = Template(recovered.template, dict(recovered.parameters, width=.6e-3), mesh=recovered.mesh_options)
    changed = reopened.update_design('a', SavedExecutionRequest(edited.dumps()))
    assert changed.current_record('a') is None and changed.design('a')['records'] == [record.to_dict()]
    assert reopened.current_record('a').receipt == receipt


def test_defaults_mesh_options_and_snapshots_are_resolved_and_detached():
    parameters = dict(PARAMS)
    mesh = dict(MESH)
    doc = Template('stripline', parameters, mesh=mesh)
    parameters['width'] = 99
    mesh['edge_size'] = 99
    assert doc.parameters['width'] == PARAMS['width'] and doc.mesh_options['edge_size'] == MESH['edge_size']
    assert doc.parameters['thickness'] == 0. and doc.parameters['box_width'] is None
    values = doc.to_dict()
    values['parameters']['width'] = 99
    copied = doc.parameters
    copied['eps_r'] = 99
    assert doc.parameters['eps_r'] == 4. and doc.parameters['width'] == PARAMS['width']
    with pytest.raises(FrozenInstanceError):
        doc._data_json = '{}'
    assert doc.section.width == doc.cross_section.section.width


def test_changed_factory_geometry_is_rejected_instead_of_silently_migrated(monkeypatch):
    doc = stripline()
    factory = _TEMPLATES['stripline']
    @wraps(factory)
    def altered(**parameters):
        return factory(**dict(parameters, width=parameters['width']*1.1))
    monkeypatch.setitem(_TEMPLATES, 'stripline', altered)
    with pytest.raises(ValueError, match='do not match'):
        Template.loads(doc.dumps())


def test_explicit_mesh_edit_is_new_valid_input_but_missing_resolved_controls_reject():
    data = stripline().to_dict()
    data['cross_section']['mesh']['edge_size'] /= 2
    edited = Template.from_dict(data)
    assert edited.mesh_options['edge_size'] == MESH['edge_size']/2
    del data['cross_section']['mesh']['far_size']
    with pytest.raises(ValueError, match='do not match'):
        Template.from_dict(data)


@pytest.mark.parametrize('where', ['parameters', 'geometry', 'boundary', 'version'])
def test_inconsistent_saved_shape_or_template_rejects(where):
    data = stripline().to_dict()
    if where == 'parameters':
        data['parameters']['width'] *= 1.1
    elif where == 'geometry':
        data['cross_section']['traces'][0]['width'] *= 1.1
    elif where == 'boundary':
        data['cross_section']['box']['sides'] = 'ground'
    else:
        data['schema'] = 'sipi.template-section/2'
    with pytest.raises(ValueError):
        Template.from_dict(data)


@pytest.mark.parametrize('parameters', [None, [], {}, dict(PARAMS, unknown=1),
    dict(PARAMS, width=True), dict(PARAMS, width=None), dict(PARAMS, width='0.5'),
    dict(PARAMS, width=-1), dict(PARAMS, width=float('nan')), dict(PARAMS, width=float('inf'))])
def test_invalid_parameters_reject(parameters):
    with pytest.raises(ValueError):
        Template('stripline', parameters)


@pytest.mark.parametrize('name', ['', 'eval', [], None, True])
def test_invalid_template_names_reject(name):
    with pytest.raises(ValueError):
        Template(name, PARAMS)


@pytest.mark.parametrize('where', ['root', 'parameters', 'cross_section', 'mesh'])
def test_unknown_fields_reject(where):
    data = stripline().to_dict()
    objects = dict(root=data, parameters=data['parameters'], cross_section=data['cross_section'],
                   mesh=data['cross_section']['mesh'])
    objects[where]['unknown'] = 1
    with pytest.raises(ValueError):
        Template.from_dict(data)


@pytest.mark.parametrize('text', ['{"schema":1,"schema":2}', '{"x":NaN}', '{"x":1e999}', '[]', 'null'])
def test_strict_json_rejects(text):
    with pytest.raises(ValueError):
        Template.loads(text)


def test_shared_byte_limits_and_unsupported_diagnostics_before_fields(monkeypatch):
    doc = stripline()
    text = doc.dumps()
    def forbidden(*args, **kwargs):
        pytest.fail('input rejection reached fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    assert normalize_saved(text, max_input_bytes=len(text.encode())) == text
    with pytest.raises(ValueError, match='max_input_bytes'):
        normalize_saved(text, max_input_bytes=len(text.encode())-1)
    with pytest.raises(ValueError, match='diagnostics require'):
        execute_saved(text, diagnostics=['modes'])
    assert 'sipi.template-section/1' in saved_schemas() and len(saved_schemas()) == 111


def test_existing_goal_and_study_inputs_reuse_template_parameters_exactly_without_solving(monkeypatch):
    from sipi.design_document import ImpedanceDesignDocument
    from sipi.study import ImpedanceStudyDocument
    doc = stripline()
    def forbidden(*args, **kwargs):
        pytest.fail('goal/study input preparation reached fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    goal = dict(variable='width', bounds=[.4e-3, .8e-3], target=50.,
                max_evaluations=32, mesh=doc.mesh_options)
    study = dict(quantity='z0', mesh=doc.mesh_options,
                 sampling=dict(kind='corners', variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]))
    assert ImpedanceDesignDocument(doc.template, doc.parameters, **goal).dumps() == ImpedanceDesignDocument('stripline', PARAMS, **goal).dumps()
    assert ImpedanceStudyDocument(doc.template, doc.parameters, **study).dumps() == ImpedanceStudyDocument('stripline', PARAMS, **study).dumps()
