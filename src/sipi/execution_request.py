# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Immutable saved inputs and controls for host-owned execution lifecycles."""
from dataclasses import dataclass, field
import hashlib
import json

from sipi.execution import (
    _integer, _load, execute_saved,
    TransmissionLineDocument, VolumeLineDocument, PanelTransmissionLineDocument,
)

__all__ = ['SavedExecutionRequest']


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False)


def _sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class SavedExecutionRequest:
    """Freeze a strict saved input and generic execution options without fields.

    Semantic identity includes the canonical input and all execution controls,
    not source formatting, invocation identity or engine/dependency artifacts.
    Hosts still own run tokens, cancellation, stale-response checks and artifact
    provenance. Neither identity nor preparation certifies physical accuracy,
    platform support, per-model budget admission, runtime or memory requirements.

    The exact original text is retained for execution so canonical formatting
    cannot inflate a previously admitted input beyond its byte limit.
    """
    source_text: str = field(repr=False)
    max_input_bytes: int = 262144
    max_evaluations: int = 128
    diagnostics: tuple[str, ...] = ()
    input_json: str = field(init=False, repr=False)
    input_sha256: str = field(init=False)
    request_id: str = field(init=False)

    def __post_init__(self):
        _integer('max_evaluations', self.max_evaluations, 2, 10000)
        values = self.diagnostics
        if (not isinstance(values, (tuple, list))
                or any(not isinstance(x, str) or x not in ('characteristic', 'modes') for x in values)
                or len(set(values)) != len(values)):
            raise ValueError('diagnostics must contain unique characteristic/modes selections')
        doc = _load(self.source_text, self.max_input_bytes)
        if values and not isinstance(doc, (
                TransmissionLineDocument, VolumeLineDocument, PanelTransmissionLineDocument)):
            raise ValueError('diagnostics require a top-level transmission-line, volume-line or panel-line')
        object.__setattr__(self, 'diagnostics', tuple(sorted(values)))
        canonical = doc.dumps()
        object.__setattr__(self, 'input_json', canonical)
        object.__setattr__(self, 'input_sha256', _sha256(canonical))
        envelope = dict(schema='sipi.execution-request/1', input=json.loads(canonical),
                        controls=self.controls)
        object.__setattr__(self, 'request_id', _sha256(_canonical(envelope)))

    @property
    def controls(self):
        """Return a fresh JSON-compatible execution-options snapshot."""
        return dict(max_input_bytes=self.max_input_bytes,
                    max_evaluations=self.max_evaluations, diagnostics=list(self.diagnostics))

    def to_dict(self):
        """Return identity, canonical input and controls, with no artifact claim."""
        return dict(schema='sipi.execution-request/1', request_id=self.request_id,
                    input_sha256=self.input_sha256, input=json.loads(self.input_json),
                    controls=self.controls)

    def run(self):
        """Execute frozen inputs; preserve existing output and original exceptions.

        Receipts identify semantic requests, not unique runs. Hosts must compare
        their own run token as well when the same request is started repeatedly.
        """
        output = execute_saved(self.source_text, max_input_bytes=self.max_input_bytes,
                               max_evaluations=self.max_evaluations,
                               diagnostics=self.diagnostics)
        if output['input'] != json.loads(self.input_json):
            raise RuntimeError('execution input differs from the frozen request')
        return dict(schema='sipi.execution-receipt/1', request=self.to_dict(), execution=output)
