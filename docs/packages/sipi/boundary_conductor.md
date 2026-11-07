# Different metals on signal and reference boundaries

[한국어](../../locales/ko/pages/packages/sipi/boundary_conductor.md)

`sipi.boundary_conductor.surface_conductor_loss_by_boundary` reuses one PEC
vacuum current solve while assigning each named signal its own `SurfaceMetal`.
One additional metal applies to **all reference surfaces together**. This is
the existing first-order surface-impedance perturbation with distinct boundary
laws, not a finite-metal diffusion solve or an independent foil-face model.

```python
import numpy as np
from sipi import microstrip
from sipi.boundary_conductor import SurfaceMetal, surface_conductor_loss_by_boundary
from sipi.roughness import CausalHuray

section = microstrip(width=.5e-3, substrate_height=1e-3,
                     thickness=35e-6, eps_r=4.)
name = next(t.name for t in section.traces if not t.ground)
loss = surface_conductor_loss_by_boundary(section, [1e9, 4e9],
    conductors={name: SurfaceMetal(58e6, roughness=CausalHuray([.2e-6], [2.]))},
    reference=SurfaceMetal(45e6, roughness_rms=.5e-6), ground_thickness=35e-6,
    edge_size=2.5e-6, far_size=.1e-3, grade=.05)
assert loss.skin_depth.shape == (2, 2)
assert loss.boundary_labels == ("signal:"+name, "reference")
np.testing.assert_allclose(loss.resistance_parts.sum(axis=1), loss.R, rtol=1e-12)
```

## Inputs and numerical meaning

`SurfaceMetal(conductivity, relative_permeability=1, roughness_rms=0,
roughness=None)` is immutable. Conductivity is positive S/m; relative
permeability is positive. RMS roughness in metres selects the existing
Hammerstad resistance-only correction. Alternatively supply `CausalHuray`,
`CannonballHuray` or `GroissRMS` with zero `roughness_rms`. Their existing
parameter definitions and limitations remain in force: Groiss is noncausal,
and Cannonball requires explicit ten-point Rz. No conversion or foil fitting
is inferred. See [roughness](roughness.md).

`conductors` must map exactly the non-ground trace names to metals. Mapping
insertion order is immaterial; the section's signal order determines output.
`reference` also covers explicit ground traces and all section ground
boundaries. Different top/bottom/signal sidewalls cannot be assigned separately.

Every metal independently requires positive frequencies and
`sigma/(omega*eps0) >= 1000`. Before meshing, each signal's skin depth must be
at most its own minimum trace dimension divided by five. Reference uses the
minimum of supplied physical `ground_thickness`, section width and every
explicit ground trace's minimum dimension. Section width also bounds signal
dimensions. Thin/zero-thickness conductors fail. A highly conductive signal
cannot conceal an invalid reference skin depth. These gates are necessary,
not complete curvature, roughness or perturbation error bounds.

For each boundary b, the existing unit-current field supplies a real matrix
`Q_b = integral(K_i K_j ds)` in 1/m. Then
`R = sum_b Re(Zs_b) Q_b` in ohm/m and
`L_internal = sum_b Im(Zs_b) Q_b / omega` in H/m.
The matrix terms include shared-return and mutual contributions; no scalar
average roughness factor is substituted. Integrated current disagreement
above 5% is rejected. Loss convergence must be checked separately.

## Results and validation scope

`BoundaryConductorLoss` preserves read-only frequency, R, internal L, complex
`surface_impedance`, skin depths, resistance roughness factors and the original
`SurfaceCurrentFactors`. Metal arrays have shape `(frequency, signals+1)`, with
signal order followed by reference. `metals` preserves those immutable input
records. `boundary_labels` uses `signal:<name>` and final `reference`.
`resistance_parts` has shape `(frequency, boundary, signal, signal)` and sums
to R. No single roughness multiplier describes this matrix in general.

`loss.network(C=..., G=..., length=..., z_ref=...)` combines R and internal L
with external L from the same vacuum field. Supply C/G for the **same geometry**;
this helper cannot infer that independently provided matrices match the mesh.
The exterior is nonmagnetic; the different permeabilities affect only the
conductor half-space laws. A supplied result object is not an accuracy certificate.

Tests compare distinct-metal uniform plates with the exact current and
independent scikit-rf surface law at `1e-10`; separate coax boundary factors and
combined impedance must converge below 2%. Identical metal assignments recover
the previous common-metal API within `1e-12`, including each supported roughness
law. A coupled PCB case checks asymmetric diagonal losses, mutual/return terms,
PSD, reciprocity/passivity, refined mesh and doubled lateral box width at 5%.
The latter is a finite set of convergence checks, not a universal loss error bar
or convergence in every exterior direction. Empirical foil accuracy, resolved
rough geometry, independent conductor faces and Gradient roughness are outside
this contract. Application integration remains separate from the engine API.

## Saved shared-mesh line

`TransmissionLineDocument` schema `sipi.transmission-line/3` adds
`conductor.kind="surface-boundaries"`. Its exact conductor fields are `kind`,
`conductors`, `reference` and `ground_thickness`. Each named signal and the
reference record requires exactly `conductivity`, `relative_permeability` and
an explicit `roughness` object (smooth, Hammerstad, Groiss, causal-Huray or
Cannonball-Huray). No default metal or missing signal is inferred.

```python
from sipi import CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.execution import execute_saved

geometry = CrossSectionDocument(section,
    mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
model = TransmissionLineDocument(geometry, [1e9, 4e9], materials={}, length=.03,
    schema="sipi.transmission-line/3",
    conductor=dict(kind="surface-boundaries", ground_thickness=35e-6,
        conductors={name: dict(conductivity=58e6, relative_permeability=1.,
            roughness=dict(kind="causal-huray", radii_m=[.2e-6], surface_ratios=[2.]))},
        reference=dict(conductivity=45e6, relative_permeability=1.,
            roughness=dict(kind="hammerstad", rms_m=.5e-6))))
saved = model.dumps()
report = execute_saved(saved)
parts = report["result"]["conductor_boundaries"]
assert parts["labels"] == ["signal:"+name, "reference"]
np.testing.assert_allclose(np.array(parts["resistance_ohm_per_m"]).sum(axis=1),
                           report["result"]["R_ohm_per_m"], rtol=1e-12)
```

Normalization validates every requested metal/frequency before meshing. Analysis
uses one mesh and the same vacuum C0/current factors for dielectric and conductor
extraction. R/L/G/C and S retain their existing units and port ordering. Existing
network/circuit inputs with `kind="transmission-line"` can contain this document.
Versions 1 and 2 retain their contracts and the constructor default remains 1.
Version 3 also accepts perfect metal and the version-2 common surface record.

Shared execution adds `conductor_boundaries` only for this distinct-metal model:
labels, `skin_depth_m`, `roughness_factor`, complex `surface_impedance_ohms` and
`resistance_ohm_per_m` contributions. Per-boundary records remain in the canonical
input. Saved replay is checked against the standalone boundary/dielectric APIs
at relative `1e-10` for RLGC and absolute `1e-10` for S, with a one-mesh assertion
and terminal-circuit replay. This composition does not strengthen the physical
validity limits or advance an application's pinned engine.
