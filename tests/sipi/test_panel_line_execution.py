# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved panel-line input/output contract and failures before field work."""
import json
import numpy as np
import pytest
import sipi.panel_line as panel_line
from sipi import CrossSection
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from sipi.modes import ModeTrackingError
from test_panel_line import base


def decoded(value):
    return np.array(value['real'])+1j*np.array(value['imag'])


@pytest.mark.parametrize('perfect',[False,True])
def test_common_execution_preserves_method_matrices_and_diagnostics(perfect):
    doc=PanelTransmissionLineDocument(base(perfect),panels_per_edge=16)
    assert doc.to_dict()['schema'] in saved_schemas()
    assert normalize_saved(doc.dumps())==doc.dumps()
    direct=doc.analyze()
    out=execute_saved(doc.dumps(),diagnostics=['characteristic'])
    assert out['input']==doc.to_dict() and out['status']=='complete' and out['error'] is None
    values=out['result']
    for key,attribute in [('R_ohm_per_m','R'),('L_h_per_m','L'),('C_f_per_m','C'),('G_s_per_m','G')]:
        np.testing.assert_array_equal(values[key],getattr(direct,attribute))
    np.testing.assert_array_equal(decoded(values['network']['s']),direct.network.s)
    np.testing.assert_array_equal(decoded(values['diagnostics']['characteristic']['z_characteristic']),direct.characteristic().z_characteristic)
    current=values['current_solver']
    assert current['kind']=='grounded-rectangle-panels' and current['settings']==doc.panel_options
    assert current['ground_trace_names']==list(direct.current_factors.ground_trace_names)
    assert current['diagnostics']==dict(direct.current_factors.diagnostics)
    for key,attribute in [('vacuum_capacitance_f_per_m','C0'),('surface_current_factors_per_m','parts'),('current_integrals','current_integrals')]:
        np.testing.assert_array_equal(current[key],getattr(direct.current_factors,attribute))
    if perfect:assert 'conductor_boundaries' not in values
    else:
        np.testing.assert_array_equal(values['conductor_boundaries']['resistance_ohm_per_m'],direct.conductor.resistance_parts)
        assert values['conductor_boundaries']['labels']==list(direct.conductor.boundary_labels)
    assert json.loads(json.dumps(out,allow_nan=False))==out


def test_frequency_budget_rejects_before_any_field_solve(monkeypatch):
    data=PanelTransmissionLineDocument(base()).to_dict();data['line']['frequency_hz']=[1e9,2e9,3e9]
    doc=PanelTransmissionLineDocument.from_dict(data)
    def forbidden(*args,**kwargs):raise AssertionError('budget check came after field work')
    monkeypatch.setattr(panel_line,'panel_conductor_loss_by_boundary',forbidden)
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError,match='frequency count exceeds max_evaluations'):
        execute_saved(doc.dumps(),max_evaluations=2)


def test_failed_optional_modes_retain_base_line_and_current_metadata(monkeypatch):
    doc=PanelTransmissionLineDocument(base(),panels_per_edge=16)
    def unresolved(self):raise ModeTrackingError('unresolved test mode',index=1,frequency=2e9)
    monkeypatch.setattr(panel_line.PanelTransmissionLineResult,'modes',unresolved)
    out=execute_saved(doc.dumps(),diagnostics=['modes'])
    assert out['status']=='complete' and out['result']['current_solver']['settings']==doc.panel_options
    diagnostic=out['result']['diagnostics']['modes']
    assert diagnostic['status']=='failed' and diagnostic['error']['index']==1
    assert diagnostic['error']['frequency_hz']==2e9
