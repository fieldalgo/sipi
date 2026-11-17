# Saved two-active transmission line with a fixed-potential guard

`TwoGroundHarmonicGuardCornerFacePanelTransmissionLineDocument` in
`sipi.two_ground_harmonic_guard_corner_face_panel_line` uses the distinct schema
`sipi.two-ground-harmonic-guard-corner-face-panel-transmission-line/1`.
It accepts exactly two active finite rectangular/tapered traces and one
`ground=True` finite guard between grounded bottom/top planes and open sides.
The guard is held at zero potential. This does not model a floating guard,
a finite ground termination or a longitudinal via connection.

The saved SI input contains a cross-section document and dielectric mesh controls,
positive frequencies, dielectric material laws, four metals per active trace,
explicit bottom/top/guard surface laws, ground thickness, length, reference
impedance and harmonic panel controls. A guard law can cover its whole perimeter
or specify four distinct faces. Normalization validates strict nested keys,
material/skin-depth/core admission, geometry and resource budgets without fields
or optional shared-solver imports. Defaults are32 panel subdivisions,256 ground
modes and interpolation degree24, with the current adapter's512-panel cap.

Analysis uses the exact selected two-current basis for vacuum C0, whole/face
current factors and surface R/internal L. Guard induced currents and losses
remain present. A mesh of the same physical section computes dielectric C/G,
including nonuniform and dispersive materials. External L uses matched C0;
network construction adds internal L once. The resulting two-conductor RLGC
matrices form a reciprocal passive four-port network for the tested passive
inputs. Numerical passivity checks do not establish measured accuracy.

The result retains canonical input, actual dielectric mesh, explicit panel
controls and detached SI current records. The face record kind is
`two-ground-harmonic-corner-faces-fixed-guard`, and its whole record kind is
`two-ground-harmonic-corner-fixed-guard`. Surface labels distinguish both planes
and every guard face. Arrays and settings retain the existing immutable result
contract. Numerical completion alone does not establish panel or outer-domain
convergence; those require separate comparisons.

`normalize_saved`, `SavedExecutionRequest`, `SavedExecutionRecord`, `SavedProject`
and the existing CLI accept this schema. Requests preserve explicit frequency
budgets, diagnostics and replay inputs. Current, mesh, dielectric and network
failures retain typed stages, canonical input and only the work actually
completed. Reopening a stored record does not recalculate or invent missing work.
Existing saved schemas and their default solvers are unchanged.

Validation includes strict field-free admission and canonical round trips,
homogeneous C/G and inverse-C0 identities, independent transmission-state network
construction, nonuniform public dielectric extraction on identical observed
meshes, selected physical metal laws, actual request/CLI/project replay and
stage-specific failure records. The separate guard adapter and shared field
carry physical-current and independent geometry-reference evidence. This line
schema does not add target search, tolerance studies, arbitrary geometry,
measured-material qualification or another-platform validation by itself.

[Guard current adapter](two_ground_harmonic_guard_corner_conductor.md) ·
[한국어](../../locales/ko/pages/packages/sipi/two_ground_harmonic_guard_corner_face_panel_line.md)
