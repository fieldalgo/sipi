# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit corner samples, unchanged accounting and independent field checks."""
from dataclasses import FrozenInstanceError
import json
import numpy as np
import pytest
from scipy.constants import epsilon_0, mu_0
from sipi import CrossSection, CornerCrossSectionDocument, CornerImpedanceStudyDocument as Document
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import ConstantDielectric
from sipi.execution import execute_saved, normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
import sipi.impedance_material as material
from test_corner_mesh_control import independent_capacitance

PARAMETERS = dict(width=.0006, plane_spacing=.002, eps_r=4., thickness=.0004, box_width=.008)
MESH = dict(edge_size=1e-5, far_size=.0002, grade=.15)


def document(sampling=None):
    study = ImpedanceStudyDocument('stripline', PARAMETERS, quantity='z0', mesh=MESH,
        sampling=sampling or dict(kind='sweep', count=2,
            variables=[dict(name='width', lower=.00055, upper=.00065)]))
    return Document(study, 2.5e-6)


def observation(result):
    return dict(quantity=result.quantity, input=json.loads(result.input_json), failed=result.failed,
        summary=None if result.summary is None else dict(result.summary),
        rows=[dict(index=row.index, parameters=dict(row.parameters), impedance=row.impedance,
            error_type=row.error_type, error=row.error,
            document=None if row.document is None else row.document.to_dict(),
            material_evaluation=None if row.material_evaluation_json is None else json.loads(row.material_evaluation_json))
              for row in result.rows])


@pytest.mark.parametrize('bad', [None, True, 0., -1., float('nan'), float('inf'), '1e-6', 2e-5])
def test_invalid_corner_rejected_without_field(bad, monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a,**k: pytest.fail('unexpected mesh'))
    raw = document().to_dict(); raw['corner_size'] = bad
    with pytest.raises(ValueError): Document.from_dict(raw)


@pytest.mark.parametrize('change', ['extra', 'missing', 'schema', 'nested', 'edge'])
def test_strict_nested_contract(change, monkeypatch):
    raw = document().to_dict()
    if change == 'extra': raw['summary'] = {}
    elif change == 'missing': del raw['study']
    elif change == 'schema': raw['schema'] = 'sipi.corner-impedance-study/2'
    elif change == 'nested': raw['study']['mesh']['corner_size'] = 1e-6
    else: raw['study']['mesh']['edge_size'] = 1e-6
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a,**k: pytest.fail('unexpected mesh'))
    with pytest.raises(ValueError): Document.from_dict(raw)


@pytest.mark.parametrize('kind', ['sweep', 'corners', 'uniform', 'normal'])
def test_sampling_is_identical_detached_and_normalized(kind, monkeypatch):
    from test_study import document as original, bounded, normal
    sampling = normal(10) if kind == 'normal' else bounded(kind, 10)
    source = original(sampling)
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a,**k: pytest.fail('unexpected mesh'))
    saved = Document(source, source.to_dict()['mesh']['edge_size']/4)
    np.testing.assert_array_equal(saved.samples(), source.samples())
    assert not saved.samples().flags.writeable
    assert saved.sample_parameters() == source.sample_parameters()
    assert saved.sample_material_evaluations() == source.sample_material_evaluations()
    assert normalize_saved(saved.dumps()) == saved.dumps()
    assert Document.loads(saved.dumps()).dumps() == saved.dumps()
    detached = saved.to_dict(); detached['corner_size'] = 999
    assert saved.corner_size != 999
    with pytest.raises(FrozenInstanceError): saved._data_json = '{}'


def test_budget_duplicate_keys_and_unsupported_original_path(monkeypatch):
    saved = document(dict(kind='sweep', count=3,
        variables=[dict(name='width', lower=.00055, upper=.00065)]))
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a,**k: pytest.fail('unexpected mesh'))
    with pytest.raises(ValueError, match='before any solve'): saved.analyze(max_evaluations=2)
    with pytest.raises(ValueError, match='before any solve'): execute_saved(saved.dumps(), max_evaluations=2)
    with pytest.raises(ValueError, match='duplicate'):
        Document.loads(saved.dumps().replace('"corner_size":','"corner_size": 1e-6, "corner_size":',1))
    with pytest.raises(ValueError): ImpedanceStudyDocument.from_dict(saved.to_dict())
    with pytest.raises(TypeError): Document({}, 1e-6)


def test_invalid_normal_rows_are_not_resampled_or_dropped(monkeypatch):
    saved = document(dict(kind='normal', count=4, seed=9, correlation=[[1]],
        variables=[dict(name='width', mean=-.001, std=1e-12)]))
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a,**k: pytest.fail('invalid row reached fields'))
    samples = saved.samples().copy()
    result = saved.analyze(max_evaluations=4)
    assert result.failed == 4 and result.summary is None
    assert [row.index for row in result.rows] == list(range(4))
    assert all(row.document is None and row.error_type == 'ValueError' for row in result.rows)
    np.testing.assert_array_equal([row.parameters['width'] for row in result.rows],samples[:,0])
    np.testing.assert_array_equal(saved.samples(), samples)
    output = execute_saved(saved.dumps(), max_evaluations=4)
    assert output['status'] == 'incomplete' and output['result']['summary'] is None


def test_duplicate_samples_and_middle_failure_keep_later_attempts(monkeypatch):
    saved = document(dict(kind='sweep', count=3,
        variables=[dict(name='width', lower=.00055, upper=.00065)]))
    monkeypatch.setattr(ImpedanceStudyDocument, 'samples', lambda self: np.full((3,1),.0006))
    calls = []
    def solve(self):
        calls.append(self.dumps())
        if len(calls) == 2: raise ArithmeticError('registered sample failure')
        return type('Line', (), dict(z0=50.))()
    monkeypatch.setattr(CornerCrossSectionDocument, 'analyze', solve)
    result = saved.analyze(max_evaluations=3)
    assert len(calls) == 3 and len(set(calls)) == 1
    assert result.failed == 1 and result.summary is None
    assert [row.complete for row in result.rows] == [True,False,True]
    assert all(row.document.corner_size == saved.corner_size for row in result.rows)
    assert result.rows[1].error_type == 'ArithmeticError'
    assert result.rows[1].error == 'registered sample failure'


@pytest.fixture(scope='module')
def geometry_results():
    saved = document(); raw = saved.to_dict()
    for key in ('edge_size', 'far_size', 'grade'): raw['study']['mesh'][key] /= 2
    raw['corner_size'] /= 2
    fine = Document.from_dict(raw)
    meshes = []; lines = []
    mesh_original = CrossSection.mesh; analyze_original = CornerCrossSectionDocument.analyze
    def mesh(self, **options):
        field = mesh_original(self, **options);meshes.append(field);return field
    def analyze(self):
        result = analyze_original(self);lines.append(result);return result
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(CrossSection, 'mesh', mesh)
        patch.setattr(CornerCrossSectionDocument, 'analyze', analyze)
        coarse_result = saved.analyze(max_evaluations=2)
        fine_result = fine.analyze(max_evaluations=2)
    assert len(meshes) == len(lines) == 4
    return saved, coarse_result, fine_result, meshes, lines


def test_actual_geometry_samples_refinement_and_independent_reference(geometry_results, record_property):
    saved, coarse, fine, meshes, lines = geometry_results
    references = [independent_capacitance(field) for field in meshes[2:]]
    record_property('corner_study_fields', json.dumps(dict(coarse=observation(coarse), fine=observation(fine),
        C0=[line.C0.tolist() for line in lines], reference_C0=references,
        meshes=[dict(nodes=f.mesh.num_nodes,triangles=f.mesh.num_triangles) for f in meshes])))
    assert not coarse.failed and not fine.failed
    assert coarse.input_json == saved.dumps()
    for index in range(2):
        a,b = lines[index],lines[index+2]
        for x,y in ((a.C0,b.C0),(a.z0,b.z0),(b.C0,references[index])):
            assert np.all(abs(x-y) <= .005*np.maximum(abs(x),abs(y)))
        for line in (a,b):
            np.testing.assert_allclose(line.C,4*line.C0,rtol=1e-9,atol=0)
            np.testing.assert_allclose(line.z0,np.sqrt(mu_0*epsilon_0)/(2*line.C0[0,0]),rtol=1e-9)
    assert coarse.rows[0].impedance > coarse.rows[1].impedance


def test_actual_material_rows_share_mesh_but_recompute_material(monkeypatch, record_property):
    source = ImpedanceStudyDocument('stripline',PARAMETERS,quantity='z0',mesh=MESH,
        frequency=1e9,materials={'dielectric':ConstantDielectric(4.)},
        material_variables={'dk':dict(region='dielectric',path=['eps_r'])},
        sampling=dict(kind='sweep',count=2,variables=[dict(name='dk',lower=3.8,upper=4.2)]))
    saved = Document(source,2.5e-6);meshes=[];samples=[]
    original_mesh=CrossSection.mesh;original_field=material._dispersive_from_mesh
    def mesh(self,**options):
        field=original_mesh(self,**options);meshes.append(field);return field
    def evaluate(field,frequency,values,**options):
        samples.append(values);return original_field(field,frequency,values,**options)
    monkeypatch.setattr(CrossSection,'mesh',mesh)
    monkeypatch.setattr(material,'_dispersive_from_mesh',evaluate)
    result=saved.analyze(max_evaluations=2)
    record_property('corner_material_fields',json.dumps(observation(result)))
    assert result.failed==0 and len(meshes)==1 and len(samples)==2
    invariant=np.array([row.impedance for row in result.rows])*np.sqrt([3.8,4.2])
    np.testing.assert_allclose(invariant,invariant[0],rtol=1e-9)
    assert result.rows[0].impedance != result.rows[1].impedance
    assert all(row.document.corner_size==saved.corner_size for row in result.rows)
    assert result.rows[0].material_evaluation_json != result.rows[1].material_evaluation_json


def test_common_execution_and_project_preserve_saved_samples(geometry_results,monkeypatch):
    saved,result,*_=geometry_results
    def replay(self,*,max_evaluations=128):
        assert self.dumps()==saved.dumps() and max_evaluations>=2
        return result
    # Reuse an observed result only for transport; do not count another field.
    monkeypatch.setattr(Document,'analyze',replay)
    request=SavedExecutionRequest(saved.dumps(),max_evaluations=2);receipt=request.run()
    assert receipt['execution']['status']=='complete'
    output=receipt['execution']['result']
    assert output['unit']=='ohm' and output['quantity']=='z0'
    assert output['rows'][0]['document']==result.rows[0].document.to_dict()
    record=SavedExecutionRecord(request,receipt,run_id='corner-study',artifacts=[
        dict(component='sipi',version='example-only',kind='wheel',sha256='1'*64)])
    project=SavedProject(request,project_id='p',design_id='a',title='Study',label='A').attach_record('a',record,select=True)
    monkeypatch.setattr(Document,'analyze',lambda *a,**k:pytest.fail('reopening solved'))
    reopened=SavedProject.loads(project.dumps())
    assert reopened.current_record('a').receipt==receipt
    assert Document.loads(reopened.prepare('a').source_text).dumps()==saved.dumps()
