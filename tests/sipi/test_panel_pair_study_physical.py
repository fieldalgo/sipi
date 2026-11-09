# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent matrix and material checks of saved paired panel sampling."""
import json
import statistics

import numpy as np

from sipi.constants import epsilon_0, mu_0
from sipi.dielectric import ConstantDielectric
from sipi.execution import execute_saved
from sipi.line_input import _line_from_values
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.study import ImpedanceStudyDocument
from test_pair_line_goal_document import source
from test_pair_line_goal import document as line_document


def run_once(monkeypatch, document):
    original = PanelTransmissionLineDocument.analyze
    calls = []
    def capture(self):
        result = original(self)
        calls.append((self.dumps(), result))
        return result
    monkeypatch.setattr(PanelTransmissionLineDocument, 'analyze', capture)
    output = execute_saved(document.dumps(), max_evaluations=4)
    assert output['status'] == 'complete' and output['input'] == document.to_dict()
    assert output['result']['count'] == len(calls) == 4 and output['result']['failed'] == 0
    json.dumps(output, allow_nan=False)
    return output['result'], calls


def check_statistics(report):
    for i, quantity in enumerate(report['quantities']):
        values = [row['values_ohm'][i] for row in report['rows']]
        summary = report['summary'][quantity]
        assert abs(summary['mean']/statistics.mean(values)-1) <= 1e-12
        assert abs(summary['sample_std']/statistics.stdev(values)-1) <= 1e-12


def test_heterogeneous_samples_against_independent_balanced_2n(monkeypatch):
    from scipy import linalg
    study = source(physical=True).to_dict()
    study['sampling']['variables'] = [dict(name='left_width', lower=.59e-3, upper=.61e-3),
                                     dict(name='gap', lower=.4e-3, upper=.42e-3)]
    conductor = line_document(.6e-3, .4e-3).to_dict()['conductor']
    document = PanelForwardPairStudyDocument(study, conductor=conductor)
    report, calls = run_once(monkeypatch, document)
    a = np.array([[1., -1.], [.5, .5]])
    for row, (text, actual) in zip(report['rows'], calls):
        direct = PanelTransmissionLineDocument(_line_from_values(study, conductor, row['sample_values']))
        assert direct.dumps() == text and row['input'] == json.loads(text)
        omega = 2*np.pi*actual.frequency[0]
        z = actual.R[0]+1j*omega*actual.L[0]
        y = actual.G[0]+1j*omega*actual.C[0]
        scale = np.sqrt(abs(z).max()/abs(y).max())
        roots, vectors = linalg.eig(np.block([[np.zeros_like(z), z/scale],
                                            [scale*y, np.zeros_like(y)]]))
        mask = roots.imag > 0
        assert np.count_nonzero(mask) == 2 and np.all(roots[mask].real >= 0)
        v = vectors[:, mask]
        reference = scale*v[:2]@np.linalg.inv(v[2:])
        matrix = actual.characteristic().z_characteristic[0]
        assert abs(matrix-reference).max()/abs(reference).max() <= 1e-10
        np.testing.assert_allclose(row['values_ohm'], np.diag(a@reference@a.T).real, rtol=1e-10, atol=0)
        assert abs((a@matrix@a.T)[0, 1]) > .001
    check_statistics(report)


def test_correlated_uniform_material_samples_against_analytic_scaling(monkeypatch):
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
    document = PanelForwardPairStudyDocument(study, conductor={'kind': 'perfect'})
    samples = document.samples()
    np.testing.assert_array_equal(samples[:, 0], samples[:, 1])
    assert len(np.unique(samples[:, 0])) == 4 and np.all(samples > 0)
    report, calls = run_once(monkeypatch, document)
    a = np.array([[1., -1.], [.5, .5]])
    for row, (_, actual), (eps, _) in zip(report['rows'], calls, samples):
        models = row['input']['line']['materials']
        assert all(models[k]['parameters']['eps_r'] == eps for k in ['substrate', 'air'])
        reference = np.sqrt(mu_0*epsilon_0/(eps*(1-1j*.02)))*np.linalg.inv(actual.current_factors.C0)
        matrix = actual.characteristic().z_characteristic[0]
        assert abs(matrix-reference).max()/abs(reference).max() <= 1e-10
        np.testing.assert_allclose(row['values_ohm'], np.diag(a@reference@a.T).real, rtol=1e-10, atol=0)
        np.testing.assert_allclose(actual.C[0], eps*actual.current_factors.C0, rtol=1e-12, atol=0)
        assert np.all(actual.R == 0)
    check_statistics(report)
