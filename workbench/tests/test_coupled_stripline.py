"""The buried-pair form uses existing geometry, differential targets and full networks."""
from pathlib import Path
import sys

import numpy as np
import pytest
import sipi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'desktop'))
from engine import execute
from sipi.template_document import TemplateSectionDocument

PARAMETERS = dict(width=.0005, gap=.0002, plane_spacing=.001, eps_r=4, thickness=0, tan_delta=0)
MESH = dict(edge_size=8e-6, far_size=.0005, grade=.3)


@pytest.fixture(scope='module')
def analyzed():
    return execute(dict(action='analyze', template='coupled_stripline', parameters=PARAMETERS, mesh=MESH))


def test_same_factory_geometry_and_homogeneous_tem_invariants(analyzed):
    direct = TemplateSectionDocument('coupled_stripline', PARAMETERS, mesh=MESH)
    assert analyzed['document'] == direct.cross_section.to_dict()
    line = analyzed['line']
    c, c0, inductance = [np.asarray(line[key]) for key in ['C', 'C0', 'L']]
    assert line['names'] == ['positive', 'negative'] and line['z_diff'] > 0
    assert 'z0' not in line
    np.testing.assert_allclose(c, 4*c0, rtol=2e-12, atol=1e-23)
    np.testing.assert_allclose(inductance@c*299792458.0**2, 4*np.eye(2), rtol=2e-12, atol=2e-12)
    np.testing.assert_allclose(c, c[::-1, ::-1], rtol=2e-3, atol=1e-15)
    assert np.linalg.eigvalsh(c).min() > 0 and c[0, 1] < 0
    assert analyzed['document']['box']['top'] == 'ground'


def test_saved_offset_taper_and_mesh_survive_width_edit_without_solving(monkeypatch):
    p = {**PARAMETERS, 'thickness':.000035, 'top_width':.0004, 'trace_height':.0003, 'box_width':.02}
    monkeypatch.setattr(sipi.CrossSection, 'mesh', lambda *a, **k: pytest.fail('save/open solved a field'))
    saved = execute(dict(action='template-document', template='coupled_stripline', parameters=p, mesh=MESH))
    opened = execute(dict(action='template-open', text=saved['document_text']))
    assert opened == saved
    edited = execute(dict(action='template-document', template='coupled_stripline',
                          parameters={**opened['parameters'], 'width':.0006}, mesh=opened['document']['mesh']))
    assert edited['document']['mesh'] == saved['document']['mesh']
    assert edited['parameters']['trace_height'] == .0003
    assert all(row['y'] == .0003 and row['width'] == .0006 for row in edited['document']['traces'])


def test_four_port_lossless_reciprocity_power_and_mixed_reference():
    settings = dict(start_hz=1e6, stop_hz=1e9, points=5, length=.1, resistance=0, z_ref=50)
    out = execute(dict(action='network', template='coupled_stripline', parameters=PARAMETERS,
                       mesh=MESH, network=settings))['network']
    assert out['ports'] == ['near:positive', 'near:negative', 'far:positive', 'far:negative']
    assert out['mixed']['z_ref'] == [100, 100, 25, 25]
    assert out['transmission'] == 'Sdd21' and out['extension'] == 's4p'
    assert out['crosstalk']['next_ports'] == [2, 1] and out['crosstalk']['fext_ports'] == [4, 1]
    values = np.asarray(out['real'])+1j*np.asarray(out['imag'])
    np.testing.assert_allclose(values, values.transpose(0, 2, 1), rtol=0, atol=2e-12)
    for value in values:
        np.testing.assert_allclose(value.conj().T@value, np.eye(4), rtol=0, atol=2e-12)


@pytest.mark.parametrize('mode', ['sweep', 'corners', 'monte_carlo'])
def test_dielectric_studies_keep_differential_quantity_and_exact_tem_scaling(mode):
    settings = dict(mode=mode, variables=[dict(parameter='eps_r', lower=3.6, upper=4.4)], points=3, seed=42)
    out = execute(dict(action='study', template='coupled_stripline', parameters=PARAMETERS,
                       mesh=MESH, study=settings))['study']
    assert out['quantity'] == 'z_diff' and out['failed'] == 0 and out['status'] == 'complete'
    assert out['settings']['points'] == (2 if mode == 'corners' else 3)
    scaled = [row['impedance']*np.sqrt(row['parameters']['eps_r']) for row in out['rows']]
    np.testing.assert_allclose(scaled, scaled[0], rtol=2e-12, atol=1e-10)
    for row in out['rows']:
        assert row['impedance'] == row['line']['z_diff']


def test_coarse_width_search_refuses_failed_refinement_with_history(analyzed):
    with pytest.raises(sipi.GoalSeekError, match='refined mesh misses target') as error:
        execute(dict(action='design', template='coupled_stripline', parameters=PARAMETERS,
                     mesh=MESH, design=dict(bounds=[.0004, .0006], target=analyzed['line']['z_diff'], tolerance=.5)))
    assert error.value.history[-1].stage == 'refinement'


def test_real_width_search_and_returned_mesh_are_differential():
    mesh = dict(edge_size=2e-6, far_size=.000125, grade=.075)
    target = execute(dict(action='analyze', template='coupled_stripline', parameters=PARAMETERS, mesh=mesh))['line']['z_diff']
    out = execute(dict(action='design', template='coupled_stripline', parameters=PARAMETERS,
                       mesh=mesh, design=dict(bounds=[.0004, .0006], target=target, tolerance=.1)))
    assert abs(out['design']['refined_residual']) <= .1 and abs(out['design']['residual']) <= .1
    # The existing goal contract returns the requested-mesh document alongside
    # a separate finer-mesh verification; do not silently substitute that mesh.
    assert abs(out['line']['z_diff']-out['design']['impedance']) < 1e-10
    assert .0004 <= out['design']['width'] <= .0006
    assert any(row['stage'] == 'refinement' for row in out['design']['history'])
    assert all(out['document']['mesh'][key] == value for key, value in mesh.items())


def test_invalid_buried_geometry_does_not_fall_back_to_surface_template(monkeypatch):
    monkeypatch.setattr(sipi.CrossSection, 'mesh', lambda *a, **k: pytest.fail('invalid input reached mesh'))
    for changes in [dict(gap=0), dict(plane_spacing=0), dict(thickness=.002), dict(trace_height=.002)]:
        with pytest.raises(ValueError):
            execute(dict(action='analyze', template='coupled_stripline', parameters={**PARAMETERS, **changes}))
