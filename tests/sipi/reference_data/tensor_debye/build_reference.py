from pathlib import Path
import json,hashlib
import numpy as np
r=Path(__file__).resolve().parent
contract=json.loads((r/'reference-contract.json').read_text());p=contract['fixture']
def rotate(values,angle):
    c,s=np.cos(angle),np.sin(angle)
    q=np.array([[c,-s],[s,c]])
    return q@np.diag(values)@q.T
base=rotate(p['eps_inf'],p['eps_inf_angle_rad'])
residues=[rotate(a,t) for a,t in zip(p['strengths'],p['angles_rad'])]
samples=np.array([base.astype(complex)+sum(a/(1+1j*f/pole) for a,pole in zip(residues,p['relaxation_hz'])) for f in p['frequency_hz']])
for a in samples:
    np.testing.assert_allclose(a,a.T,rtol=1e-14,atol=0)
    assert np.linalg.eigvalsh(a.real).min()>=1
    assert np.linalg.eigvalsh(-a.imag).min()>=-1e-12*np.max(abs(a.imag))
def commutator(a,b):return float(np.linalg.norm(a@b-b@a)/(np.linalg.norm(a)*np.linalg.norm(b)))
between=[commutator(samples[i].real,samples[j].real) for i in range(len(samples)) for j in range(i)]
within=[commutator(a.real,-a.imag) for a in samples]
assert max(between)>1e-3 and max(within)>1e-3
out=dict(status='reference-only-passed',contract_sha256=hashlib.sha256((r/'reference-contract.json').read_bytes()).hexdigest(),numpy=np.__version__,frequency_hz=p['frequency_hz'],real=samples.real.tolist(),imag=samples.imag.tolist(),real_eigenvalues=np.linalg.eigvalsh(samples.real).tolist(),loss_eigenvalues=np.linalg.eigvalsh(-samples.imag).tolist(),real_pair_commutators=between,real_loss_commutators=within,scope='Independent formula reference and analytic family proof; no candidate implementation or physical/material measurement validation.')
(r/'reference.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ['real','imag']}))
