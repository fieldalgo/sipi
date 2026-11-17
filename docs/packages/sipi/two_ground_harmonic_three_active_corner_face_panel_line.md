# Saved three-active harmonic corner face line

`TwoGroundHarmonicThreeActiveCornerFacePanelTransmissionLineDocument` from
`sipi.two_ground_harmonic_three_active_corner_face_panel_line` uses the separate schema
`sipi.two-ground-harmonic-three-active-corner-face-panel-transmission-line/1`. It connects
[three-active harmonic corner currents](two_ground_harmonic_three_active_corner_conductor.md),
existing face surface-metal laws, dielectric fields on the same section,
and a coupled3-signal RLGC/six-port network. Existing schemas and defaults remain
unchanged; normalization never silently selects this method for old inputs.

Use a `CrossSectionDocument` containing exactly three finite rectangular/tapered
Trace signals, grounded top/bottom and open sides. Each signal has explicit
bottom/top/left/right metal records. The reference has bottom/top foils,
`sides: null` and empty `conductors`. Coating, roughness, remaining metal core,
material ownership and skin-depth restrictions are unchanged. Units are SI;
the phasor convention is `exp(+j omega t)`.

Constructor arguments are `cross_section`, `frequency`, `materials`,
`conductors`, `reference`, `ground_thickness`, `length`, `z_ref` and panel
controls. Defaults are 32 subdivisions, 256 actual fine ground modes and
interpolation degree24. Each edge has six fewer physical panels than
subdivisions, with two density modes per panel. Admission checks the total
512 physical-panel budget before shared solver lookup: three Traces permit
at most48 subdivisions, and32->48 refinement stays within the same cap.
All counts are even; ground modes range64–4096 and are compared with half
that count. No resource failure triggers a coarser fallback.

`dumps`, `loads`, `from_dict` and `to_dict` preserve detached, strict JSON.
Normalization performs local admission without field solves. `analyze()`
retains R/L/G/C, the network, exact input, actual reused dielectric mesh,
and immutable current settings. The saved request, project, execution record
and CLI paths use the same document, frequency budget and calculation.
Declared artifact hashes in an imported receipt are not installed-file proof.

`current_record()` identifies `two-ground-harmonic-corner-faces-three-active`
and its nested whole-current record identifies
`two-ground-harmonic-corner-three-active`. Vacuum active-current factors
are preserved directly; dielectric layers affect C/G on the same geometry.
The current model remains a homogeneous magnetic-exterior approximation;
internal inductance is added to external inductance once.

`TwoGroundHarmonicThreeActiveCornerFacePanelLineError` retains the failed current, mesh,
dielectric or network stage, cause, exact input and completed partial work.
Saved execution preserves failures; a partial result is not complete. Other
resolution, goal and manufacturing-study schemas do not automatically select
this new engine; their explicit connection is separate work. A scalar or
paired impedance goal does not define a three-signal launch. No such target
is silently inferred from a diagonal or a selected mode.

Checks cover homogeneous C/G and inverse-inductance identities, independent
six-dimensional voltage/current network propagation, passivity, unchanged heterogeneous C/G
and mesh geometry, direct face-loss agreement, field-free admission, typed
failures and actual saved/CLI/project replay. Current-field convergence and
analytical/reference evidence remain those of the exact shared engine and
adapter. This does not qualify fixed guards, arbitrary geometry, dielectric
interface corner laws, physical coupons, browser execution or other platforms.

[한국어](../../locales/ko/pages/packages/sipi/two_ground_harmonic_three_active_corner_face_panel_line.md)
