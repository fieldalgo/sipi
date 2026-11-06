# Unequal surface pairs and forward-current impedance

`asymmetric_coupled_microstrip` gives each surface trace its own bottom width,
thickness and top width over a common grounded substrate. The left trace is
`positive`, the right is `negative`; both start at `substrate_height`. `gap` is
the bottom-edge separation. The whole bottom-width span is centred at x=0.

Required arguments are `left_width`, `right_width`, `gap`, `substrate_height`
and `eps_r`. Optional `left_thickness`/`right_thickness` default to zero,
`left_top_width`/`right_top_width` to None (rectangular), and `tan_delta` to zero.
All lengths are metres. The existing Trace contract supports centred trapezoids,
including wider tops when they do not overlap or clip the domain. Thicknesses
are nonnegative; widths/gap/heights and eps_r are positive finite numbers.
Existing geometry checks reject overlap, invalid taper and domain clipping.

Default air height is `10*substrate_height + max(thicknesses)`, measured from the
substrate surface. Default box width is `max(20*substrate_height, 4*span)`, where
`span=left_width+gap+right_width`. Both may be supplied explicitly for convergence.
Equal left/right inputs reproduce the existing `coupled_microstrip` geometry and
JSON bytes. Rectangular geometry uses v1; tapered geometry uses v2 as before.

## Explicit real forward-current target

`LineParameters.characteristic_impedance_matrix()` returns the real positive
definite matrix Zc satisfying `Zc C Zc = L`. C is `Re(C_complex)` and L is the
external inductance from vacuum C0. It reuses the checked lossless RLGC matrix
solver at reference 1 Hz; this arbitrary frequency cancels when R=G=0. The
result is a read-only snapshot and requires no additional field solve.

For two signals, `line.z_diff_forward = d^T Zc d`, with `d=[1,-1]`. It is the
ratio Vdiff/Idiff for a **forward launch with Icommon=0**, or I=[Idiff,-Idiff].
An asymmetric pair can also produce common voltage and mix components along
the line. This is not an isolated differential eigenmode. In the symmetric
limit it reduces to `2*Zodd`. The existing `even_odd()`/`z_diff` symmetry gate
is unchanged. Use [full mixed characteristic matrices](mixed_characteristic.md)
when the complex frequency-dependent RLGC response is required.

The diagnostic excludes conductor R and explicit dielectric G/C_loss. Lossy
material inputs can still affect the electrostatic field and Re(C_complex).
It is not a complex lossy impedance, DC conducting resistance, attenuation or
multi-frequency objective. Nonphysical matrices, unresolved conditioning and
unrepresentable outputs fail through the existing matrix validity checks.

## Saved tolerance and design

```python
from sipi import asymmetric_coupled_microstrip, ImpedanceDesignDocument
from sipi.study import ImpedanceStudyDocument

parameters = dict(left_width=.4e-3, right_width=.65e-3, gap=.25e-3,
    substrate_height=.5e-3, eps_r=4, left_thickness=35e-6, right_thickness=50e-6,
    left_top_width=.32e-3, right_top_width=.55e-3, tan_delta=.02,
    air_height=6e-3, box_width=12e-3)
mesh = dict(edge_size=4e-6, far_size=.25e-3, grade=.2)
study = ImpedanceStudyDocument('asymmetric_coupled_microstrip', parameters,
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='left_width', lower=.35e-3, upper=.5e-3)]),
    quantity='z_diff_forward', mesh=mesh)
saved = study.dumps()
rows = ImpedanceStudyDocument.loads(saved).analyze(max_evaluations=3)
assert all(row.complete for row in rows.rows)
goal = ImpedanceDesignDocument('asymmetric_coupled_microstrip', parameters,
    variable='left_width', bounds=[.3e-3, 1.2e-3], target=100,
    quantity='z_diff_forward', tolerance=1,
    mesh=dict(edge_size=2e-6, far_size=.125e-3, grade=.1))
result = ImpedanceDesignDocument.loads(goal.dumps()).solve()
assert abs(result.residual) <= 1 and abs(result.refined_residual) <= 1
```

The new template requires `quantity='z_diff_forward'`. All existing pair
templates also accept that explicit quantity; single-signal templates retain
`z0`, and existing symmetric pair `z_diff` behavior is unchanged. Study/design
schema fields and old canonical inputs are preserved; older readers reject the
new template or quantity. Save the exact engine commit/wheel hash with inputs.

Existing sweep, corner, uniform and correlated normal sampling retain errors
without resampling and produce a summary only if all rows complete. No per-row
mesh convergence is implied. For this unequal pair, `fixed_pitch_m` is rejected;
varying either width at fixed gap changes centre spacing. Existing equal-width
pair fixed-pitch rules remain available. Fixed total plane spacing is inapplicable.

[Fixed-frequency material overrides](material_impedance.md) remain geometry-only
for sampled/optimized variables. Tilted transverse tensors are allowed for
`z_diff_forward`, because no exchange symmetry is assumed; `z_diff` still rejects
them. Both goal endpoints must be valid and bracket the target unless one already
meets tolerance. Requested and refined mesh residuals must both meet the target.
No monotonicity, yield probability or manufacturing accuracy is guaranteed.

The tilted-material validation case illustrates why refinement is required:
starting at edge4 µm returned 100.851 Ω, but its edge2 µm replay gave 101.172 Ω,
so the 100±1 Ω goal was rejected. Starting instead at edge2 µm produced 99.995 Ω
and edge1 µm replay 100.097 Ω, meeting the unchanged tolerance. These are
observations for the specified case, not default-mesh guarantees.

## Verification and scope

Independent image-charge panels for zero-thickness vacuum strips refine 80→160
with <0.3% change. FEM coarse→fine C and forward-Z errors must decrease and end
below 2%. Independent scikit-fem complex P1 C on the same physical mesh uses
`1e-9` relative tolerance. For the documented unequal tapered pair, edge4→1 µm,
far .25→.125 mm and grade .2→.1 change complex C by <1%; separately doubling
box/air changes it by <1%. Reflection permutes C within 0.5% on independent meshes.
These numerical checks do not validate measured etching or arbitrary domains.

An independent symmetric-matrix geometric-mean formula checks Zc within `1e-10`;
scalar/symmetric limits and loss exclusion are checked separately. Saved scalar
and tilted-material correlated studies and 100-ohm width goals retain input and
requested/refined residuals within 1 ohm. Invalid dimensions and unbounded failed
rows remain visible. There is no longitudinal width variation, skew/bend/via,
automatic asymmetric eigenmode tracking or new platform validation.

[Study](study.md) · [Design](design.md) · [한국어](../../locales/ko/pages/packages/sipi/asymmetric_pair.md)
