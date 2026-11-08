# Touchstone 2.0 physical Y/Z input

**English** | [한국어](../../locales/ko/pages/packages/sipi/touchstone_parameters.md)

`loads_touchstone_parameters(text, *, z_ref, ports=None, port_names=None)` in
`sipi.touchstone` reads a strict single-ended **version 2.0 Y or Z** subset into
[LineNetwork](network.md). The required `z_ref` explicitly selects the output
positive real resistance, scalar or one per port. This is separate from the
existing [S reader](touchstone.md), whose accepted versions and parameter kind
remain unchanged. The engine performs no file or network I/O.

```python
from sipi.touchstone import loads_touchstone_parameters

text = """[Version] 2.0
# Hz Z RI R 100
[Number of Ports] 1
[Number of Frequencies] 1
[Reference] 23
[Network Data]
0 200 0
[End]
"""
network = loads_touchstone_parameters(text, z_ref=50., port_names=['terminal'])
assert abs(network.s[0, 0, 0] - (200-50)/(200+50)) < 1e-12
assert network.z_ref[0] == 50.
```

Version 2.0 Z entries are physical ohms and Y entries are physical siemens.
File `R` and `[Reference]` values are syntax-checked but do not scale these
matrices or choose the output reference. In the example, the matrix is 200ohm,
independently of file references 100ohm and 23ohm; output uses the caller's 50ohm.
This distinction follows the [IBIS Touchstone 2.0 specification, page 7](https://ibis.org/touchstone_ver2.0/touchstone_ver2_0.pdf).
Version 1.0 uses normalized non-S data and is **not accepted by this API**.
A file is never upgraded by changing a version label.

```python
# A 40ohm resistor between two terminals has rank-one Y in siemens.
y_text = """[Version] 2.0
# Hz Y RI R 123
[Number of Ports] 2
[Two-Port Data Order] 12_21
[Number of Frequencies] 1
[Network Data]
0 .025 0 -.025 0 -.025 0 .025 0
[End]
"""
series = loads_touchstone_parameters(y_text, z_ref=[50., 50.],
                                     port_names=['left', 'right'])
assert abs(series.s[0, 1, 0] - 100/140) < 1e-12
```

The reader reuses the strict lexical and matrix grammar of the S reader:
ASCII text, explicit version and option line, port/frequency counts, network
data/end blocks; RI, magnitude/degree-angle or dB/degree-angle; Hz/kHz/MHz/GHz;
full or transpose-symmetric lower/upper matrices. Two-port files require their
explicit 21_12 or 12_21 ordering. Larger full matrices are row-major. `[Reference]`
may span lines; when present it must still contain one positive real value per
port. Caller `ports`, if given, must match. Names are caller-supplied in file
order or neutral `port1`, `port2`, etc.; comments and opaque information blocks
do not assign physical connectivity. Returned arrays are copied/read-only.

The option line must explicitly select Y or Z. S, H, G, the default S option,
version 1, mixed-mode metadata, noise, unknown/duplicate keywords, malformed or
incomplete records, nonfinite values and content after `[End]` are rejected.
References must be positive real and independent of frequency. No interpolation,
extrapolation, normalization guess, fixture removal or passivity repair occurs.

Physical matrices pass directly to [impedance_network/admittance_network](parameter_network.md)
with the target reference. Their existing conditioning, cancellation, finiteness
and residual gates apply unchanged. Singular Y or Z can be valid without an
inverse of that physical matrix; a singular wave-conversion denominator is
rejected. These checks do not certify material parameters, causality or measured
accuracy. Using a synthetic or imported matrix does not establish a line model.

Verification in `tests/sipi/test_touchstone_parameters.py` covers 1–4 ports,
formats, units, nonreciprocal two-port ordering, triangular transpose symmetry,
explicit target references independent of file references, zero/open/short and
analytic scalar/series resistors. Twelve version2 file cases are read independently
by scikit-rf 2.2.0 then explicitly converted to the target references; absolute S
difference must be <=1e-12 and frequencies exact. Existing S tests remain
unchanged, and 110 pre-change S fixture outputs were checked byte-for-byte after
the shared parser refactor. The reference tool is test-only BSD-3-Clause, with
no new runtime dependency. This file-format/algebraic step has no spatial mesh
or exterior truncation; existing physical solvers are unchanged.


[Separate Touchstone2 physical H/G reader](touchstone_hybrid.md) requires two ports and explicit target references.


[Separate normalized v1 Y/Z/H/G reader](touchstone_normalized.md) restores physical units using the scalar input reference.
