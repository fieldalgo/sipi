# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved explicit panel goals on a qualified heterogeneous asymmetric pair."""
import json
import numpy as np
from scipy import linalg
from sipi.execution import execute_saved
from sipi.pair_line_goal_document import ForwardPairDesignDocument
from sipi.panel_pair_goal_document import PanelForwardPairDesignDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.line_input import _line_from_values
from test_pair_line_goal_document import document as source


def test_real_saved_goal_executes_all_refinements_with_independent_2n(monkeypatch):
    data=source(physical=True).to_dict()
    data.update(initial=[.000603169086210573,.00040941866189257275],max_evaluations=4)
    doc=PanelForwardPairDesignDocument(ForwardPairDesignDocument.from_dict(data))
    captured=[];original=PanelForwardPairDesignDocument.solve
    def solve(self):
        result=original(self);captured.append(result);return result
    monkeypatch.setattr(PanelForwardPairDesignDocument,'solve',solve)
    out=execute_saved(doc.dumps(),max_evaluations=4)
    assert out['status']=='complete' and out['input']==doc.to_dict() and out['error'] is None
    assert len(captured)==1;result=captured[0]
    assert out['result']==result.to_dict() and len(result.history)==4
    expected=PanelTransmissionLineDocument(_line_from_values(data['study'],data['conductor'],data['initial']))
    assert result.document.to_dict()==expected.to_dict()
    for line,row in [(result.result,result.history[0])]+[(r.result,r.evaluation) for r in result.refinements]:
        assert line.input_json==row.input_json
        assert np.all(abs(np.array(row.impedances)-result.targets)<=result.tolerances)
        Z=line.R[0]+2j*np.pi*line.frequency[0]*line.L[0]
        Y=line.G[0]+2j*np.pi*line.frequency[0]*line.C[0]
        scale=np.sqrt(abs(Z).max()/abs(Y).max())
        roots,vectors=linalg.eig(np.block([[np.zeros_like(Z),Z/scale],[scale*Y,np.zeros_like(Y)]]))
        mask=roots.imag>0;assert np.count_nonzero(mask)==2 and np.all(roots[mask].real>=0)
        v=vectors[:,mask];reference=scale*v[:2]@np.linalg.inv(v[2:])
        np.testing.assert_allclose(line.characteristic().z_characteristic[0],reference,rtol=1e-10,atol=1e-10)
    json.dumps(out,allow_nan=False)
