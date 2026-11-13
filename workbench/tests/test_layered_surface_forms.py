"""Surface-layer editing retains independent material and target contracts."""
import pytest
from test_extended_forms import CASES,MESH,execute,TEMPLATES,ImpedanceDesignDocument

NAMES=('layered_microstrip','coupled_layered_microstrip','asymmetric_coupled_layered_microstrip')

@pytest.mark.parametrize('name',NAMES)
def test_upper_material_study_preserves_lower_layer_and_nominal_mesh(name):
 p=CASES[name];req=dict(template=name,parameters=p,mesh=MESH,action='study',study=dict(
     mode='sweep',points=2,seed=31,variables=[dict(parameter='upper_eps_r',lower=4.8,upper=5.2)]))
 result=execute(req)['study'];q='z_diff_forward' if name.startswith('asymmetric_') else 'z_diff' if name.startswith('coupled_') else 'z0'
 assert result['quantity']==q and result['failed']==0 and len(result['rows'])==2
 assert result['rows'][1]['impedance']<result['rows'][0]['impedance']
 for row in result['rows']:
  assert row['impedance']==row['line'][q]
  assert row['document']['mesh']==result['nominal_document']['mesh']
  assert row['document']['layers'][0]['eps_r']==3.
  assert row['document']['traces'][0]['y']==.001

@pytest.mark.parametrize('name',NAMES)
def test_saved_width_goal_preserves_requested_and_refined_results(name):
 p=CASES[name];asymmetric=name.startswith('asymmetric_');pair=asymmetric or name.startswith('coupled_')
 # Use the independently qualified API mesh; the network smoke mesh is
 # insufficient for this pair's separate 0.5-ohm refinement gate.
 req=dict(template=name,parameters=p,mesh=dict(edge_size=5e-6,far_size=.25e-3,grade=.2),design=dict(bounds=[.35e-3,1.4e-3] if asymmetric else [.2e-3,1.5e-3],target=100. if pair else 75.,tolerance=.5,search_tolerance=.25,**({'variable':'left_width'} if asymmetric else {})))
 saved=execute(dict(**req,action='design-document'))['document_text']
 replay=ImpedanceDesignDocument.loads(saved).solve();result=execute(dict(**req,action='design'))
 assert result['design']['history']==[vars(r) for r in replay.history]
 assert result['design']['history'][-1]['stage']=='refinement'
 assert result['design']['refined_impedance']==replay.refined_impedance
 assert abs(replay.refined_residual)<=.5 and abs(replay.residual)<=.5
 assert ('forward_launch' in result['line'])==asymmetric


def test_coarse_pair_goal_keeps_refinement_failure_and_evaluation_history():
 from sipi.design import GoalSeekError
 name='coupled_layered_microstrip'
 req=dict(template=name,parameters=CASES[name],mesh=MESH,
          design=dict(bounds=[.2e-3,1.5e-3],target=100.,tolerance=.5,search_tolerance=.25))
 with pytest.raises(GoalSeekError,match='refined mesh misses target') as caught:
  execute(dict(**req,action='design'))
 history=caught.value.history
 assert history[-2].stage=='search' and history[-1].stage=='refinement'
 assert abs(history[-2].impedance-100.)<=.25
 assert abs(history[-1].impedance-100.)>.5
