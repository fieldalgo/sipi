# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""A cross-section mesh that passes the mesher's point limit says what to reduce."""

import pytest
from meshine import MeshSizeLimitError

from sipi import CrossSection, Layer, Trace, crosssection

H = 1e-3


def _limited(monkeypatch, max_points):
    original = crosssection.generate

    def bounded(*args, **kwargs):
        kwargs['max_points'] = max_points
        return original(*args, **kwargs)
    monkeypatch.setattr(crosssection, 'generate', bounded)


def _section(thickness=0.0):
    return CrossSection([Layer('sub', H, 4.3), Layer('air', 10 * H)],
                        [Trace('s', 0.0, 0.3 * H, H, thickness),
                         Trace('g', 0.5 * H, 0.5 * H, H, thickness, ground=True)], 20 * H)


def test_default_rule_names_the_driving_feature_and_the_settings(monkeypatch):
    _limited(monkeypatch, 50)
    section = _section()
    settings = section.mesh_settings()
    with pytest.raises(MeshSizeLimitError) as caught:
        section.mesh()
    message = str(caught.value)
    assert message.startswith('more than 50 points')
    assert type(caught.value.__cause__) is MeshSizeLimitError
    assert f"edge_size {settings['edge_size']:.4g} m" in message
    assert "gap between traces 's' and 'g'" in message and '/ 100' in message
    assert 'raise edge_size or corner_size first' in message


def test_thickness_cap_and_explicit_edge_size(monkeypatch):
    _limited(monkeypatch, 50)
    with pytest.raises(MeshSizeLimitError, match=r"trace 's' thickness / 10 cap \(5e-06 m\) / 10"):
        _section(5e-6).mesh()
    with pytest.raises(MeshSizeLimitError, match='edge_size was given explicitly'):
        _section().mesh(edge_size=H / 50)

