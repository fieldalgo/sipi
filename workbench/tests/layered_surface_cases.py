"""Create editable requests and references for the two layered surface forms."""
import json
import sys
from pathlib import Path
from engine import execute,LAYERED_SURFACE_TEMPLATES,TEMPLATES
from sipi.template_document import TemplateSectionDocument

root=Path(sys.argv[1]).resolve();root.mkdir(parents=True,exist_ok=True)
cases=json.loads((Path(__file__).resolve().parents[2]/'tests/sipi/reference_data/layered_microstrip/inputs.json').read_text())['cases']
mesh=dict(edge_size=8e-6,far_size=.3e-3,grade=.25)
settings=dict(start_hz=0.,stop_hz=2e8,points=3,length=.075,resistance=5.3,z_ref=47.)
rows=[];controls=[]
for row in cases:
 name=row['template']
 if name not in LAYERED_SURFACE_TEMPLATES: continue
 p=row['resolved_parameters'];base=dict(template=name,parameters=p,mesh=mesh)
 doc=TemplateSectionDocument(name,p,mesh=mesh);path=root/(name+'.json');path.write_text(doc.dumps())
 network=execute(dict(**base,action='network-document',network=settings))['document_text']
 network_path=root/(name+'-network.json');network_path.write_text(network)
 direct=execute(dict(**base,action='network',network=settings))
 rows.append(dict(name=name,path=str(path),input=doc.to_dict(),network_path=str(network_path),network_input=json.loads(network),direct=direct))
 if name in LAYERED_SURFACE_TEMPLATES:
  key='left_width' if 'left_width' in p else 'width';lo,hi=p[key]*.99,p[key]*1.01
  line=TEMPLATES[name](**{**p,key:lo}).analyze(**mesh)
  for kind,options in [('design',dict(bounds=[lo,hi],target=line.even_odd()['z_diff'] if name.startswith('coupled_') else line.z0,tolerance=3.,**({'variable':key} if key!='width' else {}))),
                       ('study',dict(mode='sweep',points=2,seed=31,variables=[dict(parameter=key,lower=lo,upper=hi)]))]:
   req=dict(**base,action=kind+'-document',**{kind:options});saved=execute(req)['document_text'];control_path=root/(name+'-'+kind+'.json');control_path.write_text(saved)
   direct_control=execute({**req,'action':kind})
   controls.append(dict(kind=kind,path=str(control_path),input=json.loads(saved),direct=direct_control[kind]))
(root/'cases.json').write_text(json.dumps(rows,indent=2))
(root/'controls.json').write_text(json.dumps(controls,indent=2))
