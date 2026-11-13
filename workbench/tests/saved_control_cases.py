"""Generate explicit saved-control inputs and direct runtime references."""
import json
import sys
from pathlib import Path
from engine import execute,TEMPLATES
root=Path(sys.argv[1]).resolve();root.mkdir(parents=True,exist_ok=True)
p=dict(width=.5e-3,plane_spacing=1e-3,eps_r=4.,tan_delta=.01,box_width=6e-3)
mesh=dict(edge_size=8e-6,far_size=.3e-3,grade=.25)
base=dict(template='stripline',parameters=p,mesh=mesh)
line=TEMPLATES['stripline'](**{**p,'width':.495e-3}).analyze(**mesh)
reqs=[dict(**base,action='design-document',design=dict(bounds=[.495e-3,.505e-3],target=line.z0,tolerance=3.))]
for mode in ('sweep','corners','monte_carlo'):
 reqs.append(dict(**base,action='study-document',study=dict(mode=mode,points=3,seed=31,variables=[dict(parameter='width',lower=.495e-3,upper=.505e-3)])))
reqs.append(dict(**base,action='network-document',network=dict(start_hz=1234567.89012345,stop_hz=200000000.12345678,points=3,length=.07500000000012345,resistance=5.300000000001,z_ref=47.000000000001)))
records=[]
for i,req in enumerate(reqs):
 kind=req['action'].split('-')[0];saved=execute(req)['document_text'];path=root/(str(i)+'-'+kind+'.json');path.write_text(saved)
 direct=execute({**req,'action':kind})
 records.append(dict(kind=kind,path=str(path),input=json.loads(saved),direct=direct[kind]))
(root/'cases.json').write_text(json.dumps(records,indent=2))
