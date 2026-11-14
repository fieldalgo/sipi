# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Stored P2 provenance, exact hash vector and corruption rejection."""
from pathlib import Path
import builtins
import hashlib
import json
import numpy as np
import pytest
from reference_loader import load_reference,values_digest,content_digest

ROOT=Path(__file__).parent/'reference_values/scikit_fem'


@pytest.mark.parametrize('name,count',[('three_signal_fem_shape.json',3),('four_signal_fem_shape.json',4)])
def test_record_identity_shape_self_checks_and_no_reference_import(name,count,monkeypatch):
    real_import=builtins.__import__
    def checked(name,*a,**kw):
        if name=='skfem' or name.startswith('skfem.'):pytest.fail('stored check imported the reference tool')
        return real_import(name,*a,**kw)
    monkeypatch.setattr(builtins,'__import__',checked)
    reference=load_reference(ROOT/name);record=reference.record
    assert record['references'][0]['version']=='12.0.2' and record['references'][0]['license']=='BSD-3-Clause'
    assert record['inputs']['signals']==count and record['comparison']=='different-discretization'
    assert reference.arrays['C0'].shape==(count,count) and reference.arrays['parts'].shape==(2,count+1,count,count)
    assert np.linalg.eigvalsh(reference.arrays['C0']).min()>0
    parts=reference.arrays['parts'];scale=np.max(abs(parts),axis=(-1,-2))
    assert np.min(np.linalg.eigvalsh(parts)/scale[:,:,None])>=-1e-10
    assert not any(array.flags.writeable for array in reference.arrays.values())
    assert record['generator']['product_commit']=='b0559b2fcae6344194c57818b78f0141f5b873c1'
    assert record['consumers']==['tests/sipi/test_reference_fem_shape_multisignal.py']
    script=ROOT/'compare_multisignal.py'
    assert hashlib.sha256(script.read_bytes()).hexdigest()==record['reproduction']['sha256']


def test_shared_reference_hash_vector():
    values={'x':np.array([.1,.2],dtype='<f8'),'z':np.array([1+2j],dtype='<c16')}
    digest=values_digest(values)
    assert digest=='5b1e6695fa1d3df431519ed94c7096a82b5d1ca875872559f67e1cab86e1ce2e'
    assert content_digest({'eps':{'real':4.,'imag':-.04},'modes':2},digest)=='63ad3eaeaed8bee68b8cc4ff62997c2fddd92f443327e07d926189d5fde7dea0'


@pytest.mark.parametrize('kind',['value','input','version','nonfinite','gate','private','null-reason','digest','duplicate'])
def test_corrupted_observations_cannot_pass_loading(tmp_path,kind):
    original=(ROOT/'three_signal_fem_shape.json').read_text();raw=json.loads(original)
    if kind=='value':raw['values'][0]['data'][0][0]*=1.01
    if kind=='input':raw['inputs']['signals']=4
    if kind=='version':raw['references'][0]['version']='>=12'
    if kind=='nonfinite':raw['values'][0]['data'][0][0]=float('nan')
    if kind=='gate':raw['gate']=1.
    if kind=='private':raw['generator']['command']='/private/location/command'
    if kind=='null-reason':raw['not_recorded'].pop(next(iter(raw['not_recorded'])))
    if kind=='digest':raw['values_sha256']='0'*64
    text=json.dumps(raw)
    if kind=='duplicate':text='{"case":"duplicate",'+original[1:]
    path=tmp_path/'record.json';path.write_text(text)
    with pytest.raises(ValueError):load_reference(path)
