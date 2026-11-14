# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fresh FEM currents against preserved, independently computed P2 observations."""
from pathlib import Path
import json
import numpy as np
import pytest
from reference_loader import load_reference
from sipi.document import CrossSectionDocument
from sipi.fem_shape_conductor import fem_shape_current_factors

ROOT=Path(__file__).parent/'reference_values/scikit_fem'


@pytest.mark.parametrize('count',[3,4])
def test_refined_three_and_four_signal_independent_energy(count,record_property):
    reference=load_reference(ROOT/('three_signal_fem_shape.json' if count==3 else 'four_signal_fem_shape.json'))
    doc=CrossSectionDocument.from_dict(reference.inputs['cross_section'])
    field=doc.section.mesh(**doc.mesh_options)
    result=fem_shape_current_factors(field.mesh,field.signals,field.ground)
    values={key:(float(value) if value.ndim==0 else value.tolist()) for key,value in reference.arrays.items()}
    record_property('multisignal_shape_energy',json.dumps(dict(names=result.names,
        original_parts=result.base.parts.tolist(),original_flux=result.current_integrals.tolist(),
        C0=result.C0.tolist(),Q=result.extension_parts.tolist(),finite_differences=result.finite_difference_parts.tolist(),
        step_m=result.step_m,diagnostics=dict(result.diagnostics),P2=values,
        reference_version=reference.record['references'][0]['version'],
        reference_license=reference.record['references'][0]['license'])))
    record_property('stored_shape_reference',json.dumps(dict(use='stored; reference tool not run',
        values_sha256=reference.record['values_sha256'],content_sha256=reference.record['content_sha256'],
        generation_cost=reference.record['cost'],provenance_status=reference.record['provenance_status'])))
    assert result.names==tuple('s'+str(i) for i in range(count))
    assert len(result.samples)==8*(count+1)
    maximum=max(float(np.max(abs(x-y))/np.max(abs(y)))
        for ex,ey in zip(result.extension_parts,reference.arrays['parts']) for x,y in zip(ex,ey))
    assert maximum<=.01
    assert np.max(abs(result.C0-reference.arrays['C0']))/np.max(abs(reference.arrays['C0']))<=.001
    # These describe the recorded reference run, not a new independent solve.
    assert max(values['residual'],values['energy_error'],*values['local_errors'],values['quadrature'])<=1e-10
