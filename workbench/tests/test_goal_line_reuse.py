"""Width-target output reuses the accepted requested solve without an extra field call."""
from pathlib import Path
import sys
import pytest
import sipi
from sipi.templates import stripline,coupled_stripline
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from engine import execute,serialize_line


@pytest.mark.parametrize('template',['stripline','coupled_stripline'])
@pytest.mark.parametrize('selected_width',[.2e-3,(.2e-3+.4e-3)/2,.4e-3],ids=['lower','interior','upper'])
def test_width_output_reuses_selected_requested_matrices(template,selected_width,monkeypatch):
    p=dict(width=.3e-3,plane_spacing=1e-3,eps_r=4,box_width=6e-3)
    if template=='coupled_stripline':p['gap']=.3e-3
    factory=stripline if template=='stripline' else coupled_stripline
    mesh=dict(edge_size=5e-6,far_size=.125e-3,grade=.15)
    target_line=factory(**{**p,'width':selected_width}).analyze(**mesh)
    target=target_line.z0 if template=='stripline' else target_line.even_odd()['z_diff']
    original=sipi.CrossSection.analyze;calls=[]
    def observed(self,**options):
        line=original(self,**options)
        calls.append(dict(width=self.traces[0].width,mesh=dict(options),line=serialize_line(line)))
        return line
    monkeypatch.setattr(sipi.CrossSection,'analyze',observed)
    result=execute(dict(action='design',template=template,parameters=p,mesh=mesh,
        design=dict(bounds=[.2e-3,.4e-3],target=target,tolerance=1.)))
    history=result['design']['history']
    assert len(calls)==len(history)
    assert result['design']['width']==selected_width
    assert history[-1]['stage']=='refinement'
    selected=next(c for c in calls[:-1] if c['width']==selected_width)
    assert result['line']==selected['line']
    assert result['document']['mesh']==factory(**p).mesh_settings(**mesh)
    assert result['document']['traces'][0]['width']==selected_width
    assert abs(result['design']['residual'])<=1. and abs(result['design']['refined_residual'])<=1.
    for key in ('edge_size','far_size','grade'):
        assert calls[-1]['mesh'][key]==mesh[key]/2
