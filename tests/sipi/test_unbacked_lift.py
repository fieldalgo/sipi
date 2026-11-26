# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Unbacked templates raise the backed stack by the lower air with exact heights.

The lower air shifts every trace and local dielectric. A shifted height that
lies on a layer interface or a trace face must equal the value the new section
computes for that interface or face, or the mesher meets two vertices a few
ulps apart and refuses the region (zero-length edge). Two-substrate stacks hit
this with ordinary inputs: (.1e-3 + .1e-3) + 2e-3 != (2e-3 + .1e-3) + .1e-3.
"""
import inspect
import pytest
from sipi import templates
from sipi._template_registry import _TEMPLATES

TYPICAL = dict(width=.3e-3, left_width=.3e-3, right_width=.25e-3, gap=.2e-3, ground_gap=.2e-3, ground_width=1e-3,
               substrate_height=.2e-3, lower_height=.1e-3, upper_height=.1e-3, eps_r=4., lower_eps_r=4.,
               upper_eps_r=3.5, thickness=35e-6, left_thickness=35e-6, right_thickness=35e-6,
               ground_thickness=35e-6, coating_height=60e-6, coating_thickness=60e-6, coating_eps_r=3.5)
NAMES = sorted(name for name in _TEMPLATES if 'unbacked' in name)
COARSE = dict(edge_size=20e-6, far_size=.5e-3, grade=.5)


def build(name):
    f = getattr(templates, name)
    return f(**{p: TYPICAL[p] for p in inspect.signature(f).parameters if p in TYPICAL})


def heights(section):
    faces = {t.y for t in section.traces} | {t.y+t.thickness for t in section.traces}
    return set(section.interfaces().tolist()) | faces, {y for r in section.dielectric_regions for _, y in r.vertices}


def test_every_unbacked_template_is_covered():
    assert len(NAMES) == 18 and sum('layered' in n for n in NAMES) == 9


@pytest.mark.parametrize('name', NAMES)
def test_shifted_heights_are_exact_and_the_section_meshes(name):
    section = build(name)
    reference, vertices = heights(section)
    tolerance = 1e-9*section.height
    for y in sorted(reference | vertices):
        near = [z for z in reference if z != y and abs(z-y) <= tolerance]
        assert not near, (name, y, near)
    meshed = section.mesh(**COARSE)
    assert len(meshed.mesh.nodes) > 0 and meshed.signals


@pytest.mark.parametrize('name', [n for n in NAMES if 'layered' in n])
def test_two_substrate_traces_sit_on_the_shared_interface(name):
    section = build(name)
    top_of_substrates = section.interfaces()[3]
    assert all(t.y == top_of_substrates for t in section.traces)
