# Corner-current line manufacturing samples

`TwoGroundCornerFaceLineQuantityStudyDocument` in
`sipi.two_ground_corner_face_line_study` stores the separate
`sipi.two-ground-corner-face-line-quantity-study/1` contract. It combines an
existing versioned impedance-study source with explicit physical face-metal
laws, two reference foils and corner-current controls. Defaults are 128 panels
per edge, 256 ground modes and interpolation degree24. It does not reinterpret
older study schemas or select this current method implicitly.

## Quantities and sampled inputs

A scalar `z0` source selects `impedance_real` in ohms or `attenuation` in Np/m.
A two-signal `z_diff_forward` source selects
`differential_forward_impedance_real` or `common_forward_impedance_real` in
ohms, from the full forward characteristic matrix. These are separate mixed
coordinate launches, not eigenmode impedances. Each sample uses one explicit
positive frequency and zero length; physical face laws and ordered signals
remain attached to their boundaries.

Existing sweep, corners, uniform and correlated-normal sample definitions,
material numeric leaves and fixed-pitch transformations retain their source
meaning. Every generated geometry must independently satisfy the explicit
one/two-signal, finite rectangular/tapered, two-ground current contract.
Unsupported templates or invalid sampled geometries are not converted to
another method. Numerical controls are explicit; sampling does not establish
mesh, current-panel or outer-domain convergence.

## Budgets, failures and saved execution

Preparation is field-free. The host budget must admit the entire requested
sample count before work. Every ordered row retains index, sampled values,
input and its completion or failure phase. Failed material/input/extraction/
diagnostic rows remain present; descriptive summaries require every row to
succeed. The result is not a manufacturing yield certificate, confidence
interval or continuous-range guarantee. Interrupts propagate.

Successful rows retain actual currents and dielectric mesh records. Typed
extraction failures retain their original cause and completed work. The
common saved execution, request, record and project routes preserve this
input and its receipts, including incomplete outcomes, without another solve
when reopened. Use the [explicit resolution comparison](two_ground_corner_face_resolution.md)
for separate numerical-axis checks and the [bounded goal API](two_ground_corner_face_line_goal.md)
for a callable one-parameter design.

## Validation scope

Structural checks cover ordered scalar/paired quantities, detached JSON,
strict keys, material sampling, invalid normal samples, budgets, all failure
phases, interrupts and saved evidence. The registered 2 GHz scalar sweep at
widths 0.55/0.60/0.65 mm compares panels128/256/512 for R, L and C0 using the
original 1% relative, zero absolute criterion. Returned propagation is checked
against independent scalar `sqrt(Z/Y)` and `sqrt(Z*Y)` identities. These are
finite selected cases, not measured-foil accuracy or platform certification.

[한국어](../../locales/ko/pages/packages/sipi/two_ground_corner_face_line_study.md)
