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
compare_spec = importlib.util.spec_from_file_location('mesh_compare',
    Path(__file__).resolve().parents[1] / 'mesh_diagnostics/compare.py')
comparison = importlib.util.module_from_spec(compare_spec)
compare_spec.loader.exec_module(comparison)


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
    p, t, outputs = comparison.first_triangle(record)
    assert record['triangle_calls'][0]['delaunay_round'] >= 0
    for expected, actual in zip(outputs, refine._triangle_data(p, t)):
        np.testing.assert_array_equal(actual, expected)
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


SQUARE = [[0., 0.], [1., 0.], [1., 1.], [0., 1.]]
DIAGONAL_A = [[0, 1, 2], [0, 2, 3]]
DIAGONAL_B = [[0, 1, 3], [1, 2, 3]]


def test_exact_square_diagonals_are_ties_and_order_is_separate():
    for scale, offset in [(1., 0.), (2.**-30, 2.**-20), (2.**30, -2.**40)]:
        points = np.asarray(SQUARE)*scale+offset
        result = comparison.compare_seeds(points, DIAGONAL_A, points, DIAGONAL_B)
        assert result['points_equal'] and not result['connectivity_equal']
        assert len(result['changed_edges']) == 2
        assert all(r['exact_cocircular'] and r['convex'] and r['alternate_edge_present']
                   for r in result['changed_edges'])
    reordered = np.asarray(DIAGONAL_A)[::-1, ::-1]
    result = comparison.compare_seeds(SQUARE, DIAGONAL_A, SQUARE, reordered)
    assert result['connectivity_equal'] and not result['ordered_triangles_equal']
    assert result['changed_edges'] == []


def test_one_ulp_noncocircular_geometry_is_not_rounded_to_a_tie():
    points = np.asarray(SQUARE)
    points[2, 1] = np.nextafter(1., 2.)
    result = comparison.compare_seeds(points, DIAGONAL_A, points, DIAGONAL_B)
    assert all(not r['exact_cocircular'] and r['incircle_sign'] != 0
               for r in result['changed_edges'])


def test_incircle_known_inside_outside_and_orientation():
    from fractions import Fraction as F
    a, b, c = [[F(v) for v in p] for p in [(0, 0), (1, 0), (0, 1)]]
    assert comparison.incircle(a, b, c, [F(1, 2), F(1, 2)]) > 0
    assert comparison.incircle(a, b, c, [F(2), F(2)]) < 0
    assert comparison.incircle(a, c, b, [F(2), F(2)]) > 0


def test_changed_coordinates_are_not_compared_by_node_index():
    result = comparison.compare_seeds(SQUARE, DIAGONAL_A, np.asarray(SQUARE)*2, DIAGONAL_B)
    assert not result['points_equal'] and result['connectivity_equal'] is None
    assert 'changed_edges' not in result


def test_bad_mesh_records_reject_invalid_predicates():
    for points, triangles in [
        (SQUARE, [[0., 1., 2.]]), (SQUARE, [[0, 1, 8]]),
        (SQUARE, [[0, 1, 1]]), (SQUARE, DIAGONAL_A*2),
        ([[0., 0.], [1., 0.], [2., 0.]], [[0, 1, 2]]),
        ([[0., 0.], [0., 0.], [1., 1.]], [[0, 1, 2]]),
        ([[0., 0.], [1., 0.], [0., float('nan')]], [[0, 1, 2]]),
    ]:
        with pytest.raises(ValueError):
            comparison.compare_seeds(points, triangles, SQUARE, DIAGONAL_A)


def test_trace_array_tampering_and_float_indices_are_rejected():
    record = diagnostics.array_record(SQUARE)
    comparison.checked_array(SQUARE, record)
    with pytest.raises(ValueError, match='checksum/shape'):
        comparison.checked_array(np.asarray(SQUARE)+1, record)
    with pytest.raises(ValueError, match='noninteger'):
        comparison.checked_array(np.asarray(DIAGONAL_A, dtype=float),
                                 diagnostics.array_record(DIAGONAL_A), integer=True)


def test_missing_trace_cases_do_not_look_like_comparison_success(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    a.mkdir()
    b.mkdir()
    with pytest.raises(ValueError, match='empty'):
        comparison.compare_directories(a, b)
    (a/'case.json').write_text('{}')
    with pytest.raises(ValueError, match='case sets differ'):
        comparison.compare_directories(a, b)
