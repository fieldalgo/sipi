# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit finite corner-current, dielectric-mesh and outer comparisons."""
from dataclasses import dataclass
from collections.abc import Mapping
import json
from .line_resolution import ResolutionEvaluation,_resolution_inputs,_compare
from .fem_shape_resolution import FEMShapeResolutionFailure,FEMShapeResolutionAssessment
from .sampling import _integer
from .two_ground_corner_face_panel_line import TwoGroundCornerFacePanelTransmissionLineDocument as Line,TwoGroundCornerFacePanelLineError

__all__=['TwoGroundCornerFaceResolutionAssessment','assess_two_ground_corner_face_line_resolution']


@dataclass(frozen=True)
class TwoGroundCornerFaceResolutionAssessment(FEMShapeResolutionAssessment):
    """Selected entrywise finite agreement, retaining each actual current/mesh."""
    def to_dict(self):
        out=super().to_dict()
        out['scope']='two-ground-corner-face-finite-resolution-not-absolute-accuracy'
        for saved,row in zip(out['evaluations'],self.evaluations):
            saved['dielectric_mesh']=row.result.mesh_record()
        return out


def _two_ground_corner_face_resolution_inputs(line,refined_panel_options,outer_documents,tolerances,
                                  refinement_factor,max_solves):
    if not isinstance(line,Line):raise TypeError('line must be a TwoGroundCornerFacePanelTransmissionLineDocument')
    if (not isinstance(outer_documents,(tuple,list)) or not outer_documents or
            any(not isinstance(doc,Line) for doc in outer_documents)):
        raise ValueError('provide one or more explicit two-ground-corner-face outer documents')
    limit=_integer(max_solves,5,16)
    if 4+len(outer_documents)>limit:
        raise ValueError('two-ground-corner-face resolution budget exceeded before any field solve')
    if not isinstance(refined_panel_options,Mapping):
        raise ValueError('refined_panel_options must explicitly specify all three panel controls')
    base=Line.loads(line.dumps());raw=base.to_dict();raw['panel']=dict(refined_panel_options)
    panel=Line.from_dict(raw);old,new=base.current_options,panel.current_options
    if any(new[k]<old[k] for k in old) or new==old:
        raise ValueError('panel controls must not decrease and at least one must increase')
    physical_outer=[]
    for doc in outer_documents:
        options=doc.current_options
        if (options['panels_per_edge']!=new['panels_per_edge'] or
            options['interpolation_degree']!=new['interpolation_degree'] or options['ground_modes']<new['ground_modes']):
            raise ValueError('outer documents must preserve joint panel resolution; only ground_modes may increase')
        raw=doc.to_dict();raw['panel']=old
        physical_outer.append(Line.from_dict(raw))
    # Compare the same concrete line type with baseline panel controls, isolating
    # physical/volume admission. Actual planned outer inputs retain their panels.
    models,prepared=_resolution_inputs(base,physical_outer,tolerances,refinement_factor,limit,document_type=Line)
    volume=prepared[1][1];raw=volume.to_dict();raw['panel']=new;joint=Line.from_dict(raw)
    stages=[('base',base,()),('volume',volume,((0,'volume'),)),
        ('panel',panel,((0,'panel'),)),('joint',joint,((1,'joint:panel'),(2,'joint:volume')))]
    stages.extend((f'outer:{i}',Line.loads(doc.dumps()),((3,f'outer:{i}'),)) for i,doc in enumerate(outer_documents))
    return models,stages


def assess_two_ground_corner_face_line_resolution(line,*,refined_panel_options,outer_documents,tolerances,
                                     refinement_factor=.5,max_solves=6):
    """Assess base, volume-only, panel-only, joint and explicit wider domains.

    Each selected R, internal/external L, C, G and C0 matrix entry/frequency
    uses ResolutionTolerance absolute + relative*max(abs(a),abs(b)), without
    a floor. Compare volume/panel with base, joint with each single axis and
    every outer input with joint. All inputs and the full-line budget are
    admitted before fields. Outer width may expand; moving either physical
    ground plane, changing materials/ports or coarsening controls is refused.

    Retain exact planned inputs and typed current/mesh failures, then stop on
    exceptions. Completed disagreement is unaccepted; interrupts propagate.
    This is finite agreement, not absolute accuracy or asymptotic convergence.
    """
    models,stages=_two_ground_corner_face_resolution_inputs(line,refined_panel_options,outer_documents,
                                               tolerances,refinement_factor,max_solves)
    evaluations=[];comparisons=[]
    for stage,doc,references in stages:
        text=doc.dumps()
        try:
            result=doc.analyze();evaluations.append(ResolutionEvaluation(stage,text,result))
            for index,label in references:
                comparisons.append(_compare(evaluations[index].result,result,models,label,index,len(evaluations)-1))
        except Exception as cause:
            details=json.dumps(cause.to_dict(),allow_nan=False) if isinstance(cause,TwoGroundCornerFacePanelLineError) else None
            failure=FEMShapeResolutionFailure(stage,text,type(cause).__name__,str(cause),details)
            return TwoGroundCornerFaceResolutionAssessment(models,evaluations,comparisons,len(stages),failure)
    return TwoGroundCornerFaceResolutionAssessment(models,evaluations,comparisons,len(stages))
