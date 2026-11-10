"""Explicit buried-pair placement retains existing geometry and numerical gates."""
from pathlib import Path
import sys
import pytest
import sipi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'desktop'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tests/sipi'))
from engine import execute
from test_offset_stripline_reference import PARAMS, COARSE, FINE, single_reference, reference_modes
from sipi.template_document import TemplateSectionDocument


@pytest.mark.parametrize('height', [.0003, .0003000000000123456])
@pytest.mark.parametrize('thickness', [0., 35e-6])
def test_placement_document_and_mesh_roundtrip_without_solving(height, thickness, monkeypatch):
    monkeypatch.setattr(sipi.CrossSection, 'mesh', lambda *a, **kw: pytest.fail('Document operation solved'))
    parameters = {**PARAMS, 'trace_height': height, 'thickness': thickness}
    result = execute(dict(action='template-document', template='offset_stripline', parameters=parameters, mesh=FINE))
    assert execute(dict(action='template-open', text=result['document_text'])) == result
    assert result['parameters']['trace_height'] == height
    expected = (parameters['plane_spacing']-thickness)/2 if height is None else height
    assert all(t['y'] == expected for t in result['document']['traces'])
    edited = execute(dict(action='template-document', template='offset_stripline', parameters={**parameters, 'width': .0004}, mesh=FINE))
    assert edited['document']['mesh'] == result['document']['mesh']
    assert edited['parameters']['trace_height'] == height


@pytest.mark.parametrize('explicit_mesh', [False, True], ids=['automatic', 'fixed'])
def test_independent_target_retains_placement_and_both_mesh_residuals(explicit_mesh):
    target = reference_modes(single_reference(), 4)['z0']
    result = execute(dict(action='design', template='offset_stripline', parameters=PARAMS,
        **({'mesh': FINE} if explicit_mesh else {}), design=dict(bounds=[.2e-3, .4e-3], target=target, tolerance=.5)))
    design = result['design']
    assert abs(design['residual']) <= .5 and abs(design['refined_residual']) <= .5
    assert design['width'] == pytest.approx(.3e-3, rel=.02)
    assert design['history'][-1]['stage'] == 'refinement'
    assert all(t['y'] == PARAMS['trace_height'] for t in result['document']['traces'])
    assert result['line']['z0'] == design['impedance']
    if explicit_mesh:
        assert result['document']['mesh'] == TemplateSectionDocument('offset_stripline', PARAMS, mesh=FINE).cross_section.to_dict()['mesh']


@pytest.mark.parametrize('mode', ['sweep', 'corners', 'monte_carlo'])
def test_explicit_height_study_preserves_spacing_and_mesh(mode):
    variables = [dict(parameter='trace_height', lower=.28e-3, upper=.32e-3)]
    if mode != 'sweep': variables.append(dict(parameter='eps_r', lower=3.8, upper=4.2))
    result = execute(dict(action='study', template='offset_stripline', parameters=PARAMS, mesh=COARSE,
        study=dict(mode=mode, variables=variables, points=3, seed=42)))['study']
    assert result['failed'] == 0 and result['status'] == 'complete' and result['quantity'] == 'z0'
    assert len(result['rows']) == (4 if mode == 'corners' else 3)
    for row in result['rows']:
        expected = TemplateSectionDocument('offset_stripline', {**PARAMS, **row['parameters']}, mesh=COARSE)
        assert row['document'] == expected.cross_section.to_dict()
        assert all(t['y'] == row['parameters']['trace_height'] for t in row['document']['traces'])
        assert row['impedance'] == row['line']['z0']


@pytest.mark.parametrize('lower,upper', [(0., .3e-3), (.3e-3, .001), (.3e-3, .00098)])
def test_height_bounds_touching_planes_are_rejected_before_fields(lower, upper, monkeypatch):
    monkeypatch.setattr(sipi.CrossSection, 'mesh', lambda *a, **kw: pytest.fail('Invalid bounds solved'))
    with pytest.raises(ValueError):
        execute(dict(action='study', template='offset_stripline', parameters={**PARAMS, 'thickness': 35e-6}, mesh=COARSE,
            study=dict(mode='sweep', variables=[dict(parameter='trace_height', lower=lower, upper=upper)], points=2, seed=42)))


@pytest.mark.parametrize('height', [None, 'omitted', 0., -.0001, .001])
def test_required_height_rejected_before_fields(height, monkeypatch):
    monkeypatch.setattr(sipi.CrossSection, 'mesh', lambda *a, **kw: pytest.fail('Invalid height solved'))
    parameters = {**PARAMS, 'trace_height': height}
    if height == 'omitted': del parameters['trace_height']
    with pytest.raises((TypeError, ValueError)):
        execute(dict(action='analyze', template='offset_stripline', parameters=parameters, mesh=COARSE))


def test_two_port_lossless_power_reciprocity_and_uniform_tem():
    import numpy as np
    settings = dict(start_hz=1e6, stop_hz=1e9, points=5, length=.1, resistance=0, z_ref=50)
    result = execute(dict(action='network', template='offset_stripline', parameters=PARAMS,
                          mesh=COARSE, network=settings))
    line, network = result['line'], result['network']
    assert line['names'] == ['signal'] and 'z_diff' not in line
    np.testing.assert_allclose(line['C'], 4*np.array(line['C0']), rtol=2e-12, atol=1e-23)
    np.testing.assert_allclose(np.array(line['L'])@line['C']*299792458.0**2, [[4]], rtol=2e-12)
    assert network['ports'] == ['near:signal', 'far:signal']
    assert network['extension'] == 's2p' and network['transmission'] == 'S21'
    assert 'mixed' not in network and 'crosstalk' not in network
    values = np.array(network['real'])+1j*np.array(network['imag'])
    np.testing.assert_allclose(values, values.transpose(0,2,1), rtol=0, atol=2e-12)
    for value in values: np.testing.assert_allclose(value.conj().T@value, np.eye(2), rtol=0, atol=2e-12)
