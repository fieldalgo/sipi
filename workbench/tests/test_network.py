"""Shared native/Worker network request limits and physical output."""
from pathlib import Path
import sys

import numpy as np
import pytest
import sipi

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from engine import execute, serialize_network

SETTINGS = dict(start_hz=1e6, stop_hz=1e9, points=5, length=.1, resistance=0, z_ref=50)
BASE = dict(action='network', template='stripline',
            parameters=dict(width=.5e-3, plane_spacing=1e-3, eps_r=4, tan_delta=.02),
            mesh=dict(edge_size=5e-6, far_size=.5e-3, grade=.2), network=SETTINGS)


def test_network_matches_engine_and_preserves_full_values():
    result = execute(BASE)
    doc = sipi.CrossSectionDocument.from_dict(result['document'])
    line = doc.analyze()
    net = sipi.quasistatic_network(line, np.linspace(1e6, 1e9, 5), length=.1, R=[[0]])
    out = result['network']
    np.testing.assert_allclose(np.array(out['real'])+1j*np.array(out['imag']), net.s, atol=1e-12)
    assert out['touchstone'] == net.touchstone()
    assert out['extension'] == 's2p' and out['transmission'] == 'S21'
    assert out['insertion_loss_db'][-1] > out['insertion_loss_db'][0]


def test_coupled_network_ports_and_mixed_reference():
    params = dict(width=.5e-3, gap=.2e-3, substrate_height=1e-3, eps_r=4)
    out = execute({**BASE, 'template':'coupled_microstrip', 'parameters':params})['network']
    assert out['ports'] == ['near:positive', 'near:negative', 'far:positive', 'far:negative']
    assert out['mixed']['z_ref'] == [100, 100, 25, 25]
    assert out['transmission'] == 'Sdd21' and out['extension'] == 's4p'
    assert np.asarray(out['real']).shape == (5, 4, 4)


@pytest.mark.parametrize('changes', [dict(points=202), dict(points=1), dict(points=True),
    dict(stop_hz=1e6), dict(start_hz=-1), dict(length=-1), dict(resistance=-1),
    dict(z_ref=0), dict(length=float('inf')), dict(extra=1)])
def test_bad_settings_fail_before_mesh(monkeypatch, changes):
    def forbidden(*args, **kwargs):
        pytest.fail('Invalid network controls reached meshing')
    monkeypatch.setattr(sipi.CrossSectionDocument, 'analyze', forbidden)
    with pytest.raises(ValueError):
        execute({**BASE, 'network':{**SETTINGS, **changes}})


def test_crosstalk_matches_independent_even_odd_abcd_waves():
    # Use exactly symmetric RLGC for the exact even/odd decomposition. A FEM
    # mesh may have small diagonal asymmetry and must retain its full matrices.
    c = np.array([[120, -30], [-30, 120]])*1e-12
    inductance = np.array([[400, 70], [70, 400]])*1e-9
    extracted = sipi.LineParameters(('positive','negative'), c,
        np.linalg.inv(inductance)/299792458.0**2, inductance, np.zeros((2,2)))
    network = serialize_network(extracted, SETTINGS)
    line = {'C':c.tolist(), 'L':inductance.tolist()}
    modal = []
    frequency = np.array(network['frequency'])
    for sign in (1, -1):
        inductance = line['L'][0][0] + sign*line['L'][0][1]
        capacitance = line['C'][0][0] + sign*line['C'][0][1]
        z = np.sqrt(inductance/capacitance)
        theta = 2*np.pi*frequency*np.sqrt(inductance*capacitance)*SETTINGS['length']
        denominator = 2*np.cos(theta)+1j*(z/50+50/z)*np.sin(theta)
        modal.append((1j*(z/50-50/z)*np.sin(theta)/denominator, 2/denominator))
    expected_next = (modal[0][0]-modal[1][0])/2
    expected_fext = (modal[0][1]-modal[1][1])/2
    actual = np.asarray(network['real'])+1j*np.asarray(network['imag'])
    np.testing.assert_allclose(actual[:, 1, 0], expected_next, rtol=0, atol=1e-9)
    np.testing.assert_allclose(actual[:, 3, 0], expected_fext, rtol=0, atol=1e-9)
    cross = network['crosstalk']
    assert cross['next_ports'] == [2, 1] and cross['fext_ports'] == [4, 1]
    np.testing.assert_allclose(10**(np.array(cross['next_db'])/20), abs(expected_next), rtol=0, atol=1e-9)
    np.testing.assert_allclose(10**(np.array(cross['fext_db'])/20), abs(expected_fext), rtol=0, atol=1e-9)
    assert 'crosstalk' not in execute(BASE)['network']


@pytest.mark.parametrize('action', ['analyze', 'network'])
def test_imported_asymmetric_pair_keeps_matrices_without_even_odd_claim(action):
    from dataclasses import replace
    section = sipi.coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3, eps_r=4)
    section = sipi.CrossSection(section.layers,
        [section.traces[0], replace(section.traces[1], width=.25e-3)],
        section.width, bottom=section.bottom, top=section.top, sides=section.sides)
    doc = sipi.CrossSectionDocument(section, mesh=BASE['mesh'])
    native = doc.analyze()
    with pytest.raises(ValueError, match='not symmetric'):
        native.even_odd()
    out = execute(dict(action=action, document=doc.to_dict(), network=SETTINGS))
    assert out['line']['C'] == native.C.tolist()
    assert out['line']['L'] == native.L.tolist()
    assert 'z_diff' not in out['line']
    assert 'not symmetric' in out['line']['scalar_summary_unavailable']
    if action == 'network':
        direct = sipi.quasistatic_network(native, np.linspace(1e6, 1e9, 5), length=.1, R=np.zeros((2,2)))
        np.testing.assert_allclose(np.asarray(out['network']['real'])+1j*np.asarray(out['network']['imag']), direct.s, atol=1e-12, rtol=0)
        assert out['network']['extension'] == 's4p'
