# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Original layered refinement/P2 criteria on detached reused mesh snapshots."""
import json

from sipi import CrossSection
import sipi.two_ground_panel_line as line
from sipi._two_ground_mesh_reuse import _mesh_reuse_scope, _SCOPE
from test_two_ground_panel_line import test_layered_dielectric_refinement_and_independent_complex_p2 as original_layered_check


def test_original_layered_refinements_and_complex_p2_on_warm_meshes(monkeypatch,record_property):
    original=line._reuse_mesh;generate=CrossSection.mesh;builds=[];hits=[]
    def make(self,**options):
        builds.append(dict(options));return generate(self,**options)
    def warm(cross,section):
        first=original(cross,section);second=original(cross,section)
        assert first is not second and first.mesh is not second.mesh
        assert line._mesh_record(first)==line._mesh_record(second)
        hits.append(cross.dumps());return second
    monkeypatch.setattr(CrossSection,'mesh',make);monkeypatch.setattr(line,'_reuse_mesh',warm)
    with _mesh_reuse_scope():original_layered_check(record_property)
    # Three distinct field meshes, then the original independent P2 reference mesh.
    assert len(builds)==4 and len(hits)==3 and len(set(hits))==3
    assert _SCOPE.get() is None
    record_property('two_ground_layered_mesh_reuse',json.dumps(dict(builds=builds,warmed_inputs=hits),sort_keys=True))
