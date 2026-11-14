"""Diagnostic source identity, observer invariance, and failure preservation."""
import importlib.util
import json
from pathlib import Path
import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('mesh_diagnostics',
    Path(__file__).resolve().parents[1] / 'mesh_diagnostics/run.py')
diagnostics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostics)


def test_payload_rejects_changed_missing_and_escaping_sources(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'a.py').write_bytes(b'original\n')
    expected = {'a.py': diagnostics.sha256(b'original\n')}
    assert diagnostics.checked_payload(root, expected) == {'a.py': b'original\n'}
    (root / 'a.py').write_bytes(b'changed\n')
    with pytest.raises(ValueError, match='checksum mismatch'):
        diagnostics.checked_payload(root, expected)
    with pytest.raises(FileNotFoundError):
        diagnostics.checked_payload(root, {'missing.py': expected['a.py']})
    with pytest.raises(ValueError, match='escapes checkout'):
        diagnostics.checked_payload(root, {'../outside.py': expected['a.py']})


def test_reviewed_manifest_and_wrong_source_are_not_silently_updated():
    data = diagnostics.manifest()
    assert len(data['tests']) == 6
    with pytest.raises(ValueError, match='wrong refine source base'):
        diagnostics.candidate_source(b'changed source\n', data)


def test_changed_probe_input_rejected_before_run(tmp_path, monkeypatch):
    data = diagnostics.manifest()
    (tmp_path / 'manifest.json').write_text(json.dumps(data))
    (tmp_path / 'candidate.patch').write_bytes((diagnostics.HERE / 'candidate.patch').read_bytes())
    (tmp_path / 'inputs.json').write_text('[]')
    monkeypatch.setattr(diagnostics, 'HERE', tmp_path)
    with pytest.raises(ValueError, match='inputs checksum mismatch'):
        diagnostics.manifest()


def test_existing_failure_report_is_never_overwritten(tmp_path):
    p = tmp_path / 'failure.json'
    diagnostics.write_json(p, {'error': 'original'})
    with pytest.raises(FileExistsError):
        diagnostics.write_json(p, {'error': 'replacement'})
    assert json.loads(p.read_text()) == {'error': 'original'}


def test_observation_preserves_actual_mesh_and_line_result():
    import meshine.refine as refine
    from meshine import Domain
    from sipi import microstrip
    section = microstrip(width=.5e-3, substrate_height=1e-3, eps_r=4.)
    mesh = dict(edge_size=.2e-3, far_size=2e-3, grade=.4)
    plain = section.mesh(**mesh)
    hooks = Domain.build, refine.Delaunay, refine._triangle_data, refine._treated_apices
    record = {}
    with diagnostics.trace_refinement(record):
        observed = section.mesh(**mesh)
    assert hooks == (Domain.build, refine.Delaunay, refine._triangle_data, refine._treated_apices)
    assert record['domains'] and record['rounds'] and record['triangle_calls']
    np.testing.assert_array_equal(observed.mesh.nodes, plain.mesh.nodes)
    np.testing.assert_array_equal(observed.mesh.triangles, plain.mesh.triangles)
    a, b = observed.line_parameters(), plain.line_parameters()
    for key in ('C', 'C0', 'C_loss', 'L'):
        np.testing.assert_array_equal(getattr(a, key), getattr(b, key))


def test_failed_observation_restores_hooks_and_keeps_partial_trace(monkeypatch):
    import meshine.refine as refine
    from meshine import Domain
    from sipi import microstrip
    def fail(*args, **kwargs):
        raise RuntimeError('simulated triangulation failure')
    monkeypatch.setattr(refine, 'Delaunay', fail)
    hooks = Domain.build, refine.Delaunay, refine._triangle_data, refine._treated_apices
    record = {}
    with pytest.raises(RuntimeError, match='triangulation failure'):
        with diagnostics.trace_refinement(record):
            microstrip(width=.5e-3, substrate_height=1e-3, eps_r=4.).mesh(
                edge_size=.2e-3, far_size=2e-3, grade=.4)
    assert record['domains'] and not record['rounds']
    assert hooks == (Domain.build, refine.Delaunay, refine._triangle_data, refine._treated_apices)
    assert not diagnostics.ACTIVE


def test_nested_observation_is_rejected_without_removing_outer_hooks():
    import meshine.refine as refine
    original = refine.Delaunay
    with diagnostics.trace_refinement({}):
        outer = refine.Delaunay
        with pytest.raises(RuntimeError, match='already active'):
            with diagnostics.trace_refinement({}):
                pytest.fail('nested trace started')
        assert refine.Delaunay is outer
    assert refine.Delaunay is original


def test_probe_rejects_wrong_variant_before_creating_output(tmp_path, monkeypatch):
    data = diagnostics.manifest()
    data['original_refine_sha256'] = '0'*64
    monkeypatch.setattr(diagnostics, 'manifest', lambda: data)
    destination = tmp_path / 'report'
    with pytest.raises(ValueError, match='installed refine bytes'):
        diagnostics.probe('original', destination)
    assert not destination.exists()


def test_runtime_comparison_reports_error_and_rejects_incomplete_cases():
    reference = dict(values={'a': 100., 'b': 50.}, relative_impedance_limit=1e-9)
    result = diagnostics.compare_impedances({'a': 100.0001, 'b': 50.}, reference)
    assert result['failed'] == ['a']
    assert result['relative_errors']['a'] == pytest.approx(1e-6, rel=1e-9)
    assert diagnostics.compare_impedances(reference['values'], reference)['failed'] == []
    with pytest.raises(ValueError, match='missing or adds cases'):
        diagnostics.compare_impedances({'a': 100.}, reference)


def test_runtime_comparison_cannot_silently_relax_existing_limit():
    with pytest.raises(ValueError, match='unexpected runtime comparison limit'):
        diagnostics.compare_impedances({'a': 1.}, dict(values={'a': 1.}, relative_impedance_limit=1e-6))
