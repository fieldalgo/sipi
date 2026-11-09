# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import numpy as np
from sipi.execution_request import SavedExecutionRequest as Request
from sipi.execution import execute_saved
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.constants import epsilon_0,mu_0
from test_panel_line import base


def decoded(value):
    return np.asarray(value['real'])+1j*np.asarray(value['imag'])


def test_actual_receipt_exact_output_and_uniform_material_invariant():
    doc=PanelTransmissionLineDocument(base(perfect=True),panels_per_edge=16)
    request=Request(doc.dumps(),max_evaluations=2,diagnostics=['characteristic'])
    receipt=request.run();expected=execute_saved(doc.dumps(),max_evaluations=2,diagnostics=['characteristic'])
    assert receipt['execution']==expected and expected['status']=='complete'
    assert receipt['request']==request.to_dict()
    result=expected['result'];c0=np.asarray(result['current_solver']['vacuum_capacitance_f_per_m'])
    reference=np.sqrt(mu_0*epsilon_0/(4.2*(1-.02j)))*np.linalg.inv(c0)
    characteristic=result['diagnostics']['characteristic'];assert characteristic['status']=='complete'
    z=decoded(characteristic['z_characteristic'])
    np.testing.assert_allclose(z,np.broadcast_to(reference,z.shape),rtol=1e-10,atol=0)
    np.testing.assert_allclose(result['C_f_per_m'],np.broadcast_to(4.2*c0,z.shape).real,rtol=1e-12,atol=0)
    s=decoded(result['network']['s']);np.testing.assert_allclose(s,s.transpose(0,2,1),rtol=0,atol=1e-10)
    assert np.linalg.svd(s,compute_uv=False).max()<=1+1e-10
