# Surface loss on separate signal faces

[한국어](../../locales/ko/pages/packages/sipi/face_conductor.md)

`sipi.face_conductor` assigns a separate existing `SurfaceMetal` law to the
bottom, top, left and right face of each finite rectangular or tapered signal
`Trace`. All reference planes and explicit ground traces still share one metal.
It integrates a single vacuum PEC current solution and retains every face's
contribution. It is a high-frequency surface perturbation, not a bulk plating or
finite-metal diffusion model.

```python
import numpy as np
from sipi import microstrip
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import TraceFaceMetals, surface_conductor_loss_by_face

section = microstrip(width=.5e-3, substrate_height=.5e-3, thickness=35e-6,
                     eps_r=4., air_height=1e-3, box_width=4e-3)
smooth = SurfaceMetal(58e6)
faces = TraceFaceMetals(bottom=SurfaceMetal(58e6, roughness_rms=.5e-6),
                       top=smooth, left=smooth, right=smooth)
result = surface_conductor_loss_by_face(section, [1e9, 4e9],
    conductors={"signal": faces}, reference=smooth, ground_thickness=35e-6,
    edge_size=2.5e-6, far_size=.1e-3, grade=.05)
assert result.boundary_labels == ("signal:signal:bottom", "signal:signal:top",
    "signal:signal:left", "signal:signal:right", "reference")
np.testing.assert_allclose(result.resistance_parts.sum(axis=1), result.R, rtol=1e-12)
```

Face names are global cross-section coordinates. Bottom/top are horizontal;
left/right follow sloped faces when `top_width` differs from bottom width.
`TraceFaceMetals.uniform(metal)` assigns one law to all four faces. Every signal
name must appear exactly once in the mapping, and every face must be supplied.
Arbitrary polygon signals and zero-thickness strips are rejected. Reference
surfaces are not split by face in this API.

## Physical contract and diagnostics

Each face uses the [existing surface-metal laws](boundary_conductor.md), including
conductivity, relative permeability, smooth metal, Hammerstad RMS, Groiss RMS,
causal Huray or Cannonball Huray. These parameters are explicit model inputs;
no Ra/Rq/Rz conversion or measured foil equivalence is inferred. Calling each
face's input a different metal does not establish a physically realizable bulk
material stack. It specifies a local surface impedance approximation.

Before any mesh is generated, each face's skin depth must be at most one fifth
of its trace's minimum thickness/face width. Reference uses the supplied ground
thickness, box width and all explicit ground-trace minimum dimensions. Positive
frequency and existing good-conductor checks remain required. This necessary
gate does not certify surface curvature, roughness scale or model accuracy.

For unit signal-current solutions Ki, each face has
`Q_face[i,j] = integral(Ki*Kj ds)` in 1/m. The implementation classifies both
endpoints of each signal metal edge against the four faces, with the mesh's
boundary tolerance. Every edge must belong to exactly one nonempty face;
ambiguous or missing classification rejects. Face products and integrated
currents must sum to their original whole-conductor values. There is one
vacuum field solve; the existing C0, external L and whole-conductor current-flux
check are preserved. Flux disagreement above 5% rejects the result. This is a
current-gradient diagnostic, not a 5% resistance accuracy guarantee.

At frequency f, `R = sum(Re(Zs_face)*Q_face)` in ohm/m and internal
`L = sum(Im(Zs_face)*Q_face)/(2*pi*f)` in H/m. No current redistribution due to
surface loss is solved. Output includes the common reference term. R and
internal L retain full mutual terms; they are not independent scalar wire losses.

For N signals there are P=4N+1 ordered face/reference entries. `frequency`, R and
internal L have shapes (F,), (F,N,N), (F,N,N). `skin_depth`, `roughness_factor`
and complex `surface_impedance` have shape (F,P). `factors.parts` is (P,N,N),
`factors.current_integrals` is (P,N), and `resistance_parts` is (F,P,N,N).
All stored arrays are read-only snapshots. `factors.base` retains the unsplit
boundary integrals; `factors.C0`, `L_external`, `names` and `current_error` expose
the same underlying vacuum model. A caller-created dataclass is not proof of
an actual extraction or physically valid geometry.

`result.network(C=..., G=..., length=..., z_ref=...)` combines these losses with
matched-geometry dielectric matrices and external+internal L through the existing
RLGC network solver. The caller must match geometry, conductor order and frequency.
This API does not itself add a saved transmission-line schema; existing saved
whole-boundary contracts remain unchanged.

## Validation and limits

Tests compare independently assembled scikit-fem vacuum gradients and face power
integrals at `1e-10`, and verify equal-face laws reproduce the existing boundary
model at `1e-12` for every supported roughness family. A wide centred stripline
checks the analytical Qbottom=Qtop≈1/(4w), Qreference≈1/(2w), with distinct face
resistivities and a 5% limit on the resulting resistance/internal inductance.
A tapered coupled case separately requires mesh/box resistance changes below
5%, preserves partition sums, reciprocity/PSD and passive-network behavior.
Changing one face's roughness is checked against its retained power contribution.
Invalid mappings, unsupported geometry, skin-depth and current-flux gates reject.

These are explicit model/geometry checks. No universal accuracy bound, reference
foil-face separation, measured roughness acceptance, finite-metal diffusion,
application integration or new platform support is claimed. Use independent mesh
and outer-domain refinement for the actual geometry and frequencies of interest.
