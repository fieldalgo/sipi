# Saved corner-power face transmission line

`TwoGroundCornerFacePanelTransmissionLineDocument`, imported from
`sipi.two_ground_corner_face_panel_line`, stores the explicit schema
`sipi.two-ground-corner-face-panel-transmission-line/1`. It connects
[corner currents](two_ground_corner_conductor.md) to the existing face-metal
surface laws, dielectric fields on the same section, and a multiconductor
RLGC network. Existing saved line schemas and defaults are unchanged.

## Input and execution

Use `CrossSectionDocument` with one or two finite rectangular or tapered
`Trace` signals, grounded upper/lower planes and open sidewalls. Grounded
traces, polygon traces and three-signal sections are refused. Every signal
requires bottom/top/left/right metal records; the reference record explicitly
supplies bottom/top foils, `sides: null` and an empty `conductors` object.
Coating, roughness, material ownership and skin-depth admission follow the
existing face law. Units are SI and the phasor convention is `exp(+j omega t)`.

The constructor takes `cross_section`, `frequency`, and keyword arguments
`materials`, `conductors`, `reference`, `ground_thickness`, `length`, `z_ref`
and the three panel controls. Defaults are `panels_per_edge=128`,
`ground_modes=256`, `interpolation_degree=24`. Subdivisions are even 16–512;
actual panels per edge are six fewer because corner patches combine intervals.
Ground modes are the actual fine count, even 64–4096, compared with half that
count. Interpolation degree is fixed at 24. Default controls do not certify
finite-resolution or physical accuracy for an arbitrary section.

`dumps`, `loads`, `from_dict` and `to_dict` preserve all controls in strict
versioned JSON. Normalization is detached, validates materials and geometry,
and does not solve fields or import the optional shared solver capability.
`analyze()` explicitly selects the new method; no fallback is performed.
`normalize_saved`, `execute_saved`, `SavedExecutionRequest` and
`SavedExecutionRecord` support the same document and actual replay. Host
artifact declarations in a saved record are not proof of installed bytes.
The existing execution frequency budget applies before fields.

## Results and limits

Results retain R/L/G/C, network matrices, exact input, actual dielectric mesh,
and immutable face-current settings. `current_record()` identifies
`two-ground-corner-power-faces-all-active`, with a nested whole-current record
identified as `two-ground-corner-power-all-active`. The vacuum current basis
is used directly; dielectric layers enter C/G and do not change its
homogeneous magnetic-exterior surface approximation. Internal inductance is
added once to external inductance.

`TwoGroundCornerFacePanelLineError` preserves the failed stage, cause, exact
input and whichever current/mesh work completed. The saved execution path
retains that failure; it does not mark a partial calculation completed.
Old resolution, goal and manufacturing-study schemas do not silently adopt
this method. Their corner-specific connection is separate work.

Selected tests compare homogeneous C/G and vacuum inverse-inductance laws,
independent voltage/current propagation, passive networks, matched
heterogeneous dielectric fields, face-metal results, strict normalization,
staged failures and real saved replay. Current accuracy evidence is limited
to the two independently qualified P3 cases described in the current adapter.
This does not qualify arbitrary geometry, dielectric-interface corner laws,
fixed-ground traces, measured foils, browser execution or additional platforms.

## Explicit finite comparisons

Use the separate [finite-resolution function](two_ground_corner_face_resolution.md) to compare current panels, dielectric mesh and wider side boundaries with explicit per-quantity allowances.

## Bounded design

Use the separate [one-parameter goal adapter](two_ground_corner_face_line_goal.md) to retain target checks and three independently required refinements.

## Manufacturing samples

The separate [saved line study](two_ground_corner_face_line_study.md) preserves geometry/material samples, physical face laws and failed rows.
