# sipi — signal and power integrity of PCB cross-sections

[Documentation](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/overview.md)

[Suite documentation](https://github.com/fieldalgo/openphysics/blob/main/docs/README.md)

Per-unit-length parameters of printed-circuit-board transmission lines from
their cross-section: layered/local dielectrics, rectangular, tapered or polygonal traces, quasi-static
(quasi-TEM) analysis on the galerkin finite-element engine with meshes from
meshine. Depends on numpy, scipy, galerkin and meshine.

```python
from sipi import CrossSection, Layer, Trace

cs = CrossSection(
    layers=[Layer("FR-4", 0.2e-3, eps_r=4.3, tan_delta=0.02), Layer("air", 4e-3)],
    traces=[Trace("sig", x=0.0, width=0.35e-3, y=0.2e-3, thickness=35e-6)],
    width=8e-3)
line = cs.analyze()
line.z0, line.eps_eff        # about 50.8 ohm and 3.13
line.C, line.L, line.G(1e9)  # per-metre matrices
```

It computes the capacitance, inductance and dielectric-conductance matrices,
single-line impedance, effective permittivity and delay, and coupled-line
even/odd modes. Results are checked against exact parallel-plate, coaxial and
Cohn stripline solutions and the Hammerstad–Jensen microstrip formulas; the
[documentation](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/overview.md) lists the observed numerical errors
and the checks a user should run (mesh refinement and box truncation).

[Templates, JSON input and target-impedance design](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/design.md)
reuse the same engine with input validation and a separate mesh-refinement check.

[Impedance tolerance studies](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/study.md) preserve correlated samples, fixed-pitch geometry, failed rows and descriptive statistics.

Power integrity: `PowerPlane` solves the DC voltage drop (IR drop) on a copper
plane fed by regulators and loaded by devices, checked against exact strip,
annulus and two-pad references.

[Uniform-line networks](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/network.md) convert explicit RLGC
to 2N-port S, differential/common waves and single-ended Touchstone 2.0 output.
Conductor resistance is a mandatory modelling input to those network functions.
[Causal surface roughness and line JSON v2](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/roughness.md)
add explicit sphere populations while preserving the version-1 input contract.

[High-frequency surface loss](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/conductor.md) separately
extracts signal/return R and internal L with explicit validity checks.

Not implemented: time-domain response, distributed AC power-plane impedance,
physical three-dimensional via transitions, crosshatched returns and layout import.

Licensed under Apache-2.0; see [LICENSE](https://github.com/fieldalgo/sipi/blob/main/LICENSE) and [NOTICE](https://github.com/fieldalgo/sipi/blob/main/NOTICE).

[Centred trapezoidal conductors and planar coatings](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/manufacturing_sections.md)
use actual polygonal geometry. Rectangular inputs retain the original mesh and JSON v1;
tapered inputs use strict JSON v2. Simple polygonal local dielectric regions use
[geometry JSON v3](docs/packages/sipi/polygon_sections.md); curved or holed mask regions are unsupported.

[Normal-thickness films](docs/packages/sipi/conformal_coating.md) cover single/pair traces and
[coplanar sections](docs/packages/sipi/conformal_coplanar.md), including finite coplanar grounds.
[Principal-axis dielectrics](docs/packages/sipi/principal_dielectrics.md) and
[full characteristic matrices](docs/packages/sipi/characteristic.md) retain explicit material and propagation limits.

Frequency-dependent dielectric models and fixed-mesh extraction are available in
`sipi.dielectric`; see the [contract and validation](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/dielectrics.md).
Conductor resistance and internal inductance are not extracted by this API.

[Frequency-line input JSON](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/line_model.md) combines geometry,
material dispersion, explicit metal loss and RLGC/S on one shared mesh.

[DC/AC metal-volume current diffusion](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/conductor_diffusion.md) extracts R and total L from finite metal regions, with an explicit magnetic boundary and skin-depth resolution gate. The matched line API below supplies the corresponding dielectric extraction.

[Matched finite-metal/dielectric RLGC and versioned JSON](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/volume_line.md)
reuse one conforming geometry, with finite material extent and explicit outer boundaries.

[Touchstone input and explicit network comparison](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/touchstone.md)
read supported single-ended S samples without guessing port correspondence or extrapolating.

[Terminated V/I and frequency crosstalk](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/termination.md) use explicit passive source/load impedances and named victim ports.

[Saved circuit inputs](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/circuit_document.md) reproduce network extraction and source/load responses in one versioned JSON document.

[Passive lumped RLC branches](docs/packages/sipi/lumped_network.md) share the network, circuit,
assembly and transformation contracts, with exact DC open/short behavior and saved inputs.
