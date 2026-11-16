# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded one-parameter two-ground-corner-face goals with separate volume/panel checks."""
from dataclasses import dataclass, replace
import json

from .line_goal import (LineQuantityDesign, LineQuantityEvaluation, LineQuantityGoalError,
                        _seek_line_quantity)
from .sampling import _integer
from ._two_ground_mesh_reuse import _mesh_reuse_scope
from .fem_shape_study import _quantity
from .two_ground_corner_face_panel_line import TwoGroundCornerFacePanelTransmissionLineDocument, TwoGroundCornerFacePanelLineError

__all__ = ['TwoGroundCornerFaceLineQuantityDesign', 'TwoGroundCornerFaceLineQuantityGoalError',
           'TwoGroundCornerFaceLineQuantityRefinement', 'seek_two_ground_corner_face_line_quantity']

def _refinements(text):
    out = {}
    for stage in ('volume-refinement', 'panel-refinement', 'joint-refinement'):
        data = json.loads(text)
        if stage != 'panel-refinement':
            for key in ('edge_size', 'far_size', 'grade'):
                data['cross_section']['mesh'][key] /= 2
        if stage != 'volume-refinement':
            data['panel']['panels_per_edge'] *= 2
        out[stage] = TwoGroundCornerFacePanelTransmissionLineDocument.from_dict(data)
    return out



class TwoGroundCornerFaceLineQuantityGoalError(LineQuantityGoalError):
    _details_json = None
    _current_json = None
    _mesh_json = None

    def to_dict(self):
        return dict(type=type(self).__name__,message=str(self),attempts=self.attempts,
            quantity=self.quantity,unit=self.unit,failed_parameter=self.failed_parameter,
            stage=self.stage,cause_type=self.cause_type,
            input=None if self.input_json is None else json.loads(self.input_json),
            history=[row.to_dict() for row in self.history],
            cause_details=None if self._details_json is None else json.loads(self._details_json),
            current_solver=None if self._current_json is None else json.loads(self._current_json),
            dielectric_mesh=None if self._mesh_json is None else json.loads(self._mesh_json))


def _decorate(error, cause, line):
    if isinstance(cause,TwoGroundCornerFacePanelLineError):
        error._details_json=json.dumps(cause.to_dict(),allow_nan=False)
    if line is not None:
        error._current_json=json.dumps(line.current_record(),allow_nan=False)
        error._mesh_json=json.dumps(line.mesh_record(),allow_nan=False)


@dataclass(frozen=True)
class TwoGroundCornerFaceLineQuantityRefinement:
    evaluation: LineQuantityEvaluation
    result: object

    @property
    def document(self):return TwoGroundCornerFacePanelTransmissionLineDocument.loads(self.evaluation.input_json)

    def to_dict(self):
        return dict(evaluation=self.evaluation.to_dict(),current_solver=self.result.current_record(),
                    dielectric_mesh=self.result.mesh_record())


@dataclass(frozen=True)
class TwoGroundCornerFaceLineQuantityDesign(LineQuantityDesign):
    refinements: tuple[TwoGroundCornerFaceLineQuantityRefinement, ...] = ()

    @property
    def document(self):return TwoGroundCornerFacePanelTransmissionLineDocument.loads(self.result.input_json)

    @property
    def refined_document(self):return TwoGroundCornerFacePanelTransmissionLineDocument.loads(self.refined_result.input_json)

    def to_dict(self):
        out=super().to_dict()
        out.update(scope='bounded-single-parameter-two-ground-corner-face-line-quantity-goal',
            current_solver=self.result.current_record(),dielectric_mesh=self.result.mesh_record(),
            refinements=[row.to_dict() for row in self.refinements])
        return out


def _relative_change(value,previous):
    return abs(value/previous-1) if previous else (0. if value==0 else float('inf'))


def _seek_two_ground_corner_face_line_quantity(factory,bounds,target,*,quantity,tolerance,max_evaluations=40):
    """Bisect one line quantity and require joint, volume and panel refinement.

    The explicit two-ground-corner-face factory has one positive variable, one positive
    frequency and zero length. Both endpoints must succeed. Reserve three of
    5..10000 attempts: joint refinement runs through the existing bounded
    search, followed by volume-only and panel-only checks on the frozen input.
    No factory recall, clipping, retry or method substitution occurs.

    Double panels and halve resolved edge/far/grade on their respective axes.
    Every refined value must meet the original absolute target, each changes
    at most .005 relative to nominal, and joint changes at most .005 relative
    to either single-axis value. A zero comparison value admits only zero.
    Ground modes, interpolation, frequency and ordered signal names stay fixed.
    Every failed attempt counts; partial fields survive and interrupts propagate.
    Finite refinement does not establish outer convergence or measured accuracy.
    """
    if not callable(factory):raise TypeError('factory must be callable')
    budget=_integer(max_evaluations,5,10000)
    settings=None
    def checked_factory(parameter):
        nonlocal settings
        doc=factory(parameter)
        if not isinstance(doc,TwoGroundCornerFacePanelTransmissionLineDocument):
            raise TypeError('factory must return TwoGroundCornerFacePanelTransmissionLineDocument')
        controls=doc.current_options
        if settings is not None and controls!=settings:
            raise ValueError('two-ground-corner-face panel controls must remain fixed across goal inputs')
        settings=controls
        _refinements(doc.dumps())
        return doc
    def joint_input(data):
        return _refinements(json.dumps(data,allow_nan=False))['joint-refinement'].to_dict()
    result=_seek_line_quantity(checked_factory,bounds,target,quantity=quantity,tolerance=tolerance,
        max_evaluations=budget-2,document_type=TwoGroundCornerFacePanelTransmissionLineDocument,
        design_type=TwoGroundCornerFaceLineQuantityDesign,error_type=TwoGroundCornerFaceLineQuantityGoalError,
        refine_input=joint_input,decorate_error=_decorate)
    history=list(result.history)
    history[-1]=replace(history[-1],stage='joint-refinement')
    checked=[TwoGroundCornerFaceLineQuantityRefinement(history[-1],result.refined_result)]
    attempts=len(history)
    def failure(message,stage,*,cause=None,text=None,line=None):
        error=TwoGroundCornerFaceLineQuantityGoalError(message,history,attempts=attempts,quantity=quantity,
            failed_parameter=result.parameter,stage=stage,cause_type=None if cause is None else type(cause).__name__,input_json=text)
        _decorate(error,cause,line)
        return error
    def convergence(value,previous,stage,line):
        if _relative_change(value,previous)>.005:
            raise failure('independent refinement exceeds relative convergence limit',stage+'/convergence',
                text=line.input_json,line=line)
    convergence(result.refined_value,result.value,'joint-refinement',result.refined_result)
    inputs=_refinements(result.document.dumps())
    for stage in ('volume-refinement','panel-refinement'):
        attempts+=1
        doc=inputs[stage];text=doc.dumps();line=None;phase='extraction'
        try:
            line=doc.analyze();phase='diagnostic'
            names=tuple(t.name for t in doc.cross_section.section.traces if not t.ground)
            value=_quantity(line,names,doc.to_dict()['frequency_hz'][0],quantity)
        except Exception as cause:
            raise failure(f'{stage} {phase} failed: {cause}',stage+'/'+phase,cause=cause,text=text,line=line) from cause
        row=LineQuantityEvaluation(result.parameter,value,stage,text);history.append(row)
        if abs(value-result.target)>result.tolerance:
            raise failure('refined input misses target',stage+'/target',text=text,line=line)
        convergence(value,result.value,stage,line)
        convergence(result.refined_value,value,stage+'/joint-check',result.refined_result)
        checked.append(TwoGroundCornerFaceLineQuantityRefinement(row,line))
    return replace(result,history=tuple(history),refinements=tuple(checked))


def seek_two_ground_corner_face_line_quantity(factory,bounds,target,*,quantity,tolerance,max_evaluations=40):
    """Seek one face-aware lossy quantity with three frozen refinements.

    The original bounded search, target and relative convergence limits apply.
    Face metal laws remain attached to physical boundaries in every refinement.
    Only dielectric meshes are reused within this operation; current solutions
    are evaluated for their exact geometry and explicit face-law document.
    """
    with _mesh_reuse_scope():
        return _seek_two_ground_corner_face_line_quantity(factory,bounds,target,quantity=quantity,
            tolerance=tolerance,max_evaluations=max_evaluations)
