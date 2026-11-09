# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed physical candidates against independent matrices and family intervals."""
from fractions import Fraction
import json

import numpy as np

from sipi.execution import execute_saved
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_selection import PanelForwardPairSelectionDocument
from test_panel_pair_yield_physical import request, Q


def test_saved_fixed_candidates_against_independent_physics_and_binomial(monkeypatch):
    from scipy import linalg
    from scipy.stats import binomtest
    base = request('geometry').to_dict()['study']
    heights = [.0005, .00052]; costs = [1., .8]; candidates = []
    for i, (height, cost) in enumerate(zip(heights, costs)):
        study = json.loads(json.dumps(base))
        study['study']['parameters']['substrate_height'] = height
        candidates.append(dict(name='candidate-'+str(i), cost=cost, study=study))
    limits = {q: dict(minimum=lo, maximum=hi) for q, (lo, hi) in zip(Q, [[100., 130.], [35., 50.]])}
    doc = PanelForwardPairSelectionDocument(candidates, cost_unit='relative-cost',
        acceptance=limits, confidence=.95, minimum_yield=.3)
    original = PanelTransmissionLineDocument.analyze; calls = []
    def capture(self):
        result = original(self); calls.append((self.dumps(), result)); return result
    monkeypatch.setattr(PanelTransmissionLineDocument, 'analyze', capture)
    output = execute_saved(doc.dumps(), max_evaluations=8); result = output['result']
    assert output['status'] == 'complete' and output['input'] == doc.to_dict()
    assert result['evaluations'] == len(calls) == 8 and result['unresolved'] == 0
    assert (1-Fraction(result['candidate_confidence']))*2 <= 1-Fraction(.95)
    a = np.array([[1., -1.], [.5, .5]]); independently_certified = []
    for index, candidate in enumerate(result['candidates']):
        labels = []; assessment = candidate['assessment']
        assert candidate['study'] == doc.to_dict()['candidates'][index]['study']
        assert len(assessment['rows']) == 4
        for row, (text, line) in zip(assessment['rows'], calls[4*index:4*(index+1)]):
            assert row['input'] == json.loads(text)
            omega = 2*np.pi*line.frequency[0]
            z = line.R[0]+1j*omega*line.L[0]; y = line.G[0]+1j*omega*line.C[0]
            scale = np.sqrt(abs(z).max()/abs(y).max())
            roots, vectors = linalg.eig(np.block([[np.zeros_like(z), z/scale], [scale*y, np.zeros_like(y)]]))
            mask = roots.imag > 0
            assert np.count_nonzero(mask) == 2 and np.all(roots[mask].real >= 0)
            v = vectors[:, mask]; reference = scale*v[:2]@np.linalg.inv(v[2:])
            full = line.characteristic().z_characteristic[0]
            assert abs(full-reference).max()/abs(reference).max() <= 1e-10
            values = np.diag(a@reference@a.T).real
            np.testing.assert_allclose(row['values_ohm'], values, rtol=1e-10, atol=0)
            labels.append('pass' if all(limits[q]['minimum'] <= value <= limits[q]['maximum']
                                       for q, value in zip(Q, values)) else 'fail')
        assert [row['classification'] for row in assessment['rows']] == labels
        interval = binomtest(labels.count('pass'), 4).proportion_ci(
            confidence_level=result['candidate_confidence'], method='exact')
        np.testing.assert_allclose(assessment['confidence_interval'], [interval.low, interval.high], rtol=0, atol=1e-12)
        goal = 'pass' if interval.low >= .3 else 'fail' if interval.high < .3 else 'undetermined'
        assert assessment['goal_status'] == goal
        if goal == 'pass': independently_certified.append(index)
    expected = min(independently_certified, key=lambda i: (costs[i], i))
    assert result['selected']['index'] == expected == 1 and result['status'] == 'selected'
    json.dumps(output, allow_nan=False)
