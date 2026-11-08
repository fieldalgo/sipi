# Lossy common-current forward-impedance goal

**English** | [한국어](../../locales/ko/pages/packages/sipi/common_forward_line_goal.md)

`common_forward_impedance_real` targets Re(Zcc) in ohms for two ordered
signals at one fixed positive frequency. It uses full lossy forward Zc,
including asymmetric geometry, dielectric and conductor laws. With u=[.5,.5],
Zcc=u Zc u^T. Coordinates are Vd=V1−V2,Vc=(V1+V2)/2,Id=(I1−I2)/2,Ic=I1+I2.
At the launch plane Id=0, so Vc=Zcc Ic and Vd=Zdc Ic. Differential voltage
generally remains nonzero; downstream Id need not remain zero.

The existing [forward matrix](characteristic.md) keeps reciprocal/passive/
conditioning guards. This quantity is a specified current launch, not an
uncoupled eigenmode, magnitude or finite-terminal input impedance. A real
objective leaves the imaginary part unconstrained. No symmetric projection
or mode tracking is introduced.

The example keeps center pitch .95mm while varying the left width. Signal
thicknesses, conductivities and roughness differ. The fixed frequency is1GHz.

```python
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_goal import seek_line_quantity

def pair(width):
    section = asymmetric_coupled_microstrip(left_width=width, right_width=.5e-3,
        gap=.95e-3-(width+.5e-3)/2, substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6, air_height=10e-3, box_width=24e-3)
    def metal(sigma, rms):
        return dict(conductivity=sigma, relative_permeability=1.,
                    roughness=dict(kind='hammerstad', rms_m=rms))
    cross = CrossSectionDocument(section,
        mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075))
    return TransmissionLineDocument(cross, [1e9], materials={}, length=0.,
        schema='sipi.transmission-line/3', conductor=dict(kind='surface-boundaries',
            conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
            reference=metal(58e6, 0.), ground_thickness=35e-6))

goal = seek_line_quantity(pair, [.2e-3, 1e-3], 40.,
    quantity='common_forward_impedance_real', tolerance=.125, max_evaluations=24)
assert max(abs(goal.residual), abs(goal.refined_residual)) <= .125
mixed = goal.result.characteristic().mixed_mode()
assert goal.value == mixed.z_characteristic[0, 1, 1].real
assert abs(mixed.z_characteristic[0, 0, 1]) > 1e-3
selected_input = goal.document.dumps()
```

Positive bounds, exact ordered names/frequency, zero length, counted factory/
validation/field/diagnostic attempts and original failure snapshots follow
[the goal API](line_goal.md). One attempt is reserved to halve edge size,
far size and grade at the selected frozen input, without recalling the
factory. Requested and refined values must meet the same absolute tolerance.
Bisection is not a proof of continuity, monotonicity, uniqueness or global
optimality. Outer-domain adequacy remains a separate check.

```python
import json
import numpy as np
zc=goal.result.characteristic().z_characteristic[0]
u=np.array([.5,.5])
np.testing.assert_allclose(goal.value,(u@zc@u).real,rtol=1e-10)
current=np.array([.5,.5])  # Ic=1 A, Id=0 A at the launch plane.
voltage=zc@current
np.testing.assert_allclose((voltage[0]+voltage[1])/2,mixed.z_characteristic[0,1,1],rtol=1e-10)
np.testing.assert_allclose(voltage[0]-voltage[1],mixed.z_characteristic[0,0,1],rtol=1e-10)
report=goal.to_dict()
assert report['scope']=='bounded-single-parameter-common-forward-line-goal'
assert report['history'][-1]['stage']=='refinement' and report['evaluations']<=24
assert goal.unit=='ohm'
json.dumps(report,allow_nan=False)
```

Independent scikit-rf2.2.0 DistributedCircuit modes with a known nonorthogonal
power-dual transform check Zc/Zcc within relative1e-10. A separate balanced2N
voltage/current telegrapher eigenspace uses positive-phase roots and the same
1e-10 gate, independently of the production Schur square root. These compare
identical RLGC, not independently extracted geometry. Symmetric common-mode
and lossless SPD geometric-mean limits, coupled differential voltage, strict
identity, budgets, frozen refinement and original errors are also checked.

The registered40ohm fixture requires requested/refined/enlarged-box residuals
<=.125ohm and outer relative change<=.005. The requested mesh uses edge2.5µm,far.25mm,grade.075; all three are
halved for refinement. Box/air increase24/10mm to36/15mm and48/20mm
using fixed refined mesh controls. Both enlarged domains must pass the same
gates, and successive absolute changes must decrease. This finite-domain trend
is not an error bound to an infinite domain. A separate24/10mm to48/20mm
trial with the earlier far.125mm (refined.0625mm) exceeded the unchanged
300000-point resource limit during outer meshing;
its original failure is retained and that full fixture remains unqualified.
The same earlier mesh reached30/12.5mm at39.9711677365ohm, but its separate
24-to30-to36mm study failed the same resource cap at36mm. It remains
unqualified as a complete outer-domain study. The new remote cap is checked
through fresh requested/refined solves; no accuracy or resource gate is relaxed.
A separate40ohm trial on12/5mm to24/10mm was
unqualified: coarse40.0317696120ohm and refined40.0497475740ohm met the
absolute gate, but enlarged39.8487339556ohm missed it by residual−.1512660444ohm.
Its relative change.00501909826 also exceeded.005. Both failed gates are
preserved. The separate original25ohm trial on12/5mm at widths.2–1mm
is unqualified: endpoint values49.0350408845/36.8947052564ohm have equal
residual signs and trigger the original bracket error after two attempts.
That rejection is preserved; it is not a global proof that no interior
solution exists. No tolerance was relaxed to turn it into a successful trial.

Six prior scalar/differential goal reports and full RLGC arrays preserve exact
source/installed hashes. Existing numerical search, extraction and matrix
formulas remain unchanged; explicit quantity selection adds common coordinate1.
Saved goal/study versions1–2 still reject this new quantity. The selected line
input is saveable, while the Python factory is not serialized. The registry
remains93schemas/37templates. No measured/full-wave accuracy, continuous-band
guarantee or app/platform update is added.
