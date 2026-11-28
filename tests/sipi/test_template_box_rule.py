# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Template default boxes: rule v2 for new calls, v1 kept for saved documents."""
import inspect
import json
import threading
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

import pytest

from sipi import CrossSectionDocument, templates
from sipi._template_registry import _TEMPLATES, _TEMPLATES_V2

TYPICAL = dict(width=.3e-3, left_width=.3e-3, right_width=.25e-3, gap=.2e-3, ground_gap=.2e-3, ground_width=1e-3,
               substrate_height=.2e-3, lower_height=.1e-3, upper_height=.1e-3, eps_r=4., lower_eps_r=4.,
               upper_eps_r=3.5, thickness=35e-6, left_thickness=35e-6, right_thickness=35e-6,
               ground_thickness=35e-6, coating_height=60e-6, coating_thickness=60e-6, coating_eps_r=3.5,
               plane_spacing=1e-3, trace_height=.4e-3, lower_width=.3e-3, upper_width=.3e-3,
               lower_top_width=.28e-3, upper_top_width=.28e-3, gap_eps_r=4., lower_thickness=35e-6,
               upper_thickness=35e-6, gap_lower_height=.1e-3, gap_lower_eps_r=4., gap_upper_eps_r=4.)
NAMES = sorted(_TEMPLATES)


def inputs(name):
    return {p: TYPICAL[p] for p in inspect.signature(_TEMPLATES[name]).parameters if p in TYPICAL}


def text(section):
    return CrossSectionDocument(section).dumps()


def raw(name, rule):
    with templates.box_rule(rule):
        return getattr(templates, name)(**inputs(name))


def test_every_template_is_covered():
    assert len(NAMES) == 72 and set(_TEMPLATES_V2) == set(NAMES)


@pytest.mark.parametrize('name', NAMES)
def test_registry_builds_v1_whatever_the_caller_rule(name):
    # Saved documents rebuild templates through the catalog; it must give the v1
    # box under any surrounding rule, and the v2 catalog the v2 box.
    v1 = text(raw(name, 'v1'))
    for rule in templates.BOX_RULES:
        with templates.box_rule(rule):
            assert text(_TEMPLATES[name](**inputs(name))) == v1
            assert text(_TEMPLATES_V2[name](**inputs(name))) == text(raw(name, 'v2'))
    assert inspect.signature(_TEMPLATES[name]) == inspect.signature(getattr(templates, name))


@pytest.mark.parametrize('name', NAMES)
def test_v2_scales_each_default_box_term(name):
    old, new = raw(name, 'v1'), raw(name, 'v2')
    air = {l.name: l.thickness for l in old.layers}, {l.name: l.thickness for l in new.layers}
    if old.top == 'ground':
        factor = 1                       # stripline families keep their box
    elif 'lower_air' in air[0]:
        factor = 2                       # unbacked: width, air and lower air
    else:
        factor = 4                       # surface with a ground plane: width and air
    assert new.width == pytest.approx(factor*old.width, rel=1e-15)
    for layer, thickness in air[0].items():
        if layer == 'lower_air' or (layer == 'air' and not old.dielectric_regions):
            assert air[1][layer] == pytest.approx(factor*thickness, rel=1e-15)
        elif layer != 'air':
            assert air[1][layer] == thickness
    if factor == 1:
        assert text(new) == text(old)


def test_default_rule_and_validation():
    assert templates.DEFAULT_BOX_RULE == 'v2' and templates.current_box_rule() == 'v2'
    with templates.box_rule('v1'):
        assert templates.current_box_rule() == 'v1'
        with templates.box_rule('v2'):
            assert templates.current_box_rule() == 'v2'
        assert templates.current_box_rule() == 'v1'
    assert templates.current_box_rule() == 'v2'
    with pytest.raises(ValueError, match='box rule'):
        with templates.box_rule('v3'):
            pass
    explicit = dict(inputs('microstrip'), box_width=5e-3, air_height=2e-3)
    assert text(templates.microstrip(**explicit)) == text(_TEMPLATES['microstrip'](**explicit))


def _registry_width(name):
    return _TEMPLATES[name](**inputs(name)).width


def test_registry_is_v1_in_new_threads_and_processes():
    # A new thread or process starts with the default rule (v2); the catalog
    # sets v1 on every call.
    expected = raw('microstrip', 'v1').width
    seen = []
    with templates.box_rule('v1'):
        worker = threading.Thread(target=lambda: seen.append((templates.current_box_rule(),
                                                                _registry_width('microstrip'))))
        worker.start(); worker.join()
    assert seen == [('v2', expected)]
    with ProcessPoolExecutor(1, mp_context=multiprocessing.get_context('spawn')) as pool:
        assert pool.submit(_registry_width, 'unbacked_coplanar').result() == raw('unbacked_coplanar', 'v1').width


def test_v2_box_truncation_on_the_worst_studied_microstrip():
    # The widest studied microstrip (w/h 4, 35 um) had +0.075 % eps_eff at the
    # v2 box against the 8x box (+0.025 % residual). Keep the v2 box within 0.1 %.
    h = .2e-3
    kw = dict(width=4*h, substrate_height=h, eps_r=4.3, thickness=35e-6)
    with templates.box_rule('v1'):
        v1 = templates.microstrip(**kw)
    mesh = v1.mesh_settings()
    mesh = dict(edge_size=mesh['edge_size'], far_size=mesh['far_size'], grade=.15)
    v2 = templates.microstrip(**kw).analyze(**mesh).eps_eff
    air = 8*v1.layers[1].thickness
    far = templates.microstrip(**kw, box_width=8*v1.width, air_height=air).analyze(**mesh).eps_eff
    assert abs(v2/far-1) < 1e-3
