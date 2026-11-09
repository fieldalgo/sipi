# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent physical matrices, joint labels and exact-binomial intervals."""
import json
import numpy as np
import pytest

from sipi.constants import epsilon_0, mu_0
from sipi.dielectric import ConstantDielectric
from sipi.execution import execute_saved
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_pair_yield import PanelForwardPairYieldDocument
from sipi.study import ImpedanceStudyDocument
from test_pair_line_goal_document import source
from test_pair_line_goal import document as line_document

Q = ('differential_forward_impedance_real', 'common_forward_impedance_real')


def request(case):
    if case == 'geometry':
        raw = source(physical=True).to_dict()
        raw['sampling'].update(kind='uniform', count=4, seed=123, variables=[
            dict(name='left_width', lower=.59e-3, upper=.61e-3),
            dict(name='gap', lower=.4e-3, upper=.42e-3)])
        conductor = line_document(.6e-3, .4e-3).to_dict()['conductor']
        paired = PanelForwardPairStudyDocument(raw, conductor=conductor)
        bounds = [[109.5, 110.5], [39.9, 40.1]]
    else:
        study = ImpedanceStudyDocument('coupled_microstrip',
            dict(width=.3e-3, gap=.2e-3, substrate_height=.5e-3, eps_r=4.,
                 thickness=35e-6, air_height=2e-3, box_width=6e-3),
            quantity='z_diff_forward', frequency=1e9,
            materials={'substrate': ConstantDielectric(3.7, .02), 'air': ConstantDielectric(3.7, .02)},
            mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
            material_variables={'dk_substrate': dict(region='substrate', path=['eps_r']),
                                'dk_air': dict(region='air', path=['eps_r'])},
            sampling=dict(kind='normal', count=4, seed=3, correlation=[[1., 1.], [1., 1.]],
                variables=[dict(name='dk_substrate', mean=3.7, std=.1),
                           dict(name='dk_air', mean=3.7, std=.1)]))
        paired = PanelForwardPairStudyDocument(study, conductor={'kind': 'perfect'})
        bounds = [[90., 100.], [50., 55.]]
    return PanelForwardPairYieldDocument(paired,
        acceptance={q: dict(minimum=lo, maximum=hi) for q, (lo, hi) in zip(Q, bounds)},
        confidence=.95, minimum_yield=.9)


@pytest.mark.parametrize('case', ['geometry', 'material'])
def test_saved_joint_yield_against_independent_matrices_and_binomial(case, monkeypatch):
    from scipy import linalg
    from scipy.stats import binomtest
    doc = request(case); original = PanelTransmissionLineDocument.analyze; calls = []
    def capture(self):
        result = original(self)
        calls.append((self.dumps(), result))
        return result
    monkeypatch.setattr(PanelTransmissionLineDocument, 'analyze', capture)
    output = execute_saved(doc.dumps(), max_evaluations=4)
    assert output['status'] == 'complete' and output['input'] == doc.to_dict()
    report = output['result']
    assert report['count'] == len(calls) == 4 and report['unresolved'] == 0
    assert report['quantities'] == list(Q)
    a = np.array([[1., -1.], [.5, .5]]); labels = []
    for row, (text, actual) in zip(report['rows'], calls):
        assert row['input'] == json.loads(text)
        if case == 'geometry':
            omega = 2*np.pi*actual.frequency[0]
            z = actual.R[0]+1j*omega*actual.L[0]; y = actual.G[0]+1j*omega*actual.C[0]
            scale = np.sqrt(abs(z).max()/abs(y).max())
            roots, vectors = linalg.eig(np.block([[np.zeros_like(z), z/scale], [scale*y, np.zeros_like(y)]]))
            mask = roots.imag > 0
            assert np.count_nonzero(mask) == 2 and np.all(roots[mask].real >= 0)
            v = vectors[:, mask]; reference = scale*v[:2]@np.linalg.inv(v[2:])
        else:
            eps, other = row['sample_values']; assert eps == other
            reference = np.sqrt(mu_0*epsilon_0/(eps*(1-1j*.02)))*np.linalg.inv(actual.current_factors.C0)
            np.testing.assert_allclose(actual.C[0], eps*actual.current_factors.C0, rtol=1e-12, atol=0)
            assert np.all(actual.R == 0)
        full = actual.characteristic().z_characteristic[0]
        assert abs(full-reference).max()/abs(reference).max() <= 1e-10
        values = np.diag(a@reference@a.T).real
        np.testing.assert_allclose(row['values_ohm'], values, rtol=1e-10, atol=0)
        limits = doc.to_dict()['acceptance']
        labels.append('pass' if all(limits[q]['minimum'] <= value <= limits[q]['maximum']
                                   for q, value in zip(Q, values)) else 'fail')
    assert [row['classification'] for row in report['rows']] == labels
    assert report['passed'] == labels.count('pass') and report['failed'] == labels.count('fail')
    ref = binomtest(labels.count('pass'), 4).proportion_ci(confidence_level=.95, method='exact')
    np.testing.assert_allclose(report['confidence_interval'], [ref.low, ref.high], rtol=0, atol=1e-12)
    assert report['sample_fraction_bounds'] == [labels.count('pass')/4]*2
    assert report['goal_status'] == 'undetermined'
    json.dumps(output, allow_nan=False)
