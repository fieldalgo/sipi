# Fixed-radius surface roughness fitting

`fit_huray` fits nonnegative full-sphere area ratios of the existing
`CausalHuray` law at **explicit fixed radii**. Supply complex surface impedance
samples in ohm/square (`resistance + j*reactance`, exp(+jωt)), known metal
conductivity in S/m and relative permeability. This operation fits a constitutive
surface model; it does not extract surface impedance from a PCB S-parameter
measurement or infer radii from Ra/Rq/Rz.

```python
import numpy as np
from sipi.conductor import surface_impedance
from sipi.roughness import CausalHuray
from sipi.roughness_fit import fit_huray

frequency = np.geomspace(1e6, 1e11, 41)
radii = [.2e-6, 1.2e-6, 4e-6]
# Synthetic demonstration; substitute independently obtained surface samples.
samples = surface_impedance(frequency, conductivity=58e6,
    roughness=CausalHuray(radii, [.7, 2., 1.5]))
result = fit_huray(frequency, resistance=samples.real, reactance=samples.imag,
    radii_m=radii, conductivity=58e6, max_error_ratio=1e-8)
assert result.accepted
print(result.model.surface_ratios)
# The model can be used wherever CausalHuray is already accepted.
assert result.maximum_error_ratio < 1e-8
```

Inputs require 2..10000 strictly increasing positive frequencies and 1..16
strictly increasing positive radii in metres. Both measured R and X must be
finite and positive; Boolean, complex or mismatched numeric arrays fail.
The existing good-conductor check remains mandatory. Positive data below the
smooth-metal response are allowed and retained as potentially incompatible
data; they are never clamped to the model.

For known smooth surface impedance `Zs`, the fit minimizes
`sum(weights * abs((Zmodel - Zinput)/Zs)**2)` with nonnegative surface ratios.
The complex sphere responses form a real stacked least-squares matrix. Its
full column rank and condition <=1e10 are required. NNLS uses a fixed budget
of 10 times the number of radii, without retries; a scaled KKT optimality error
above 1e-10 fails. All weights default to one, and multiplying every weight by
a common positive factor leaves the objective unchanged.

`accepted` means only that the **largest sampled smooth-normalized complex
error** is <= the explicit `max_error_ratio`. It is independent of objective
weights. Above-limit candidates return `accepted=False` together with every
original sample, prediction, normalized residual, weighted RMS error, condition
and KKT diagnostic. Inputs and output arrays are copied and read-only. Numerical
or input failures raise rather than producing a candidate. `to_dict()['model']`
uses the existing `causal-huray` material record.

The resulting nonnegative sphere law has its existing passive causal
continuation. Sample agreement does not establish measurement uncertainty,
parameter uniqueness under noise, continuous-band accuracy or physical validity
outside the samples. Fixed radii and conductivity/permeability are assumptions,
not fitted measurements. No automatic radius/population selection, simultaneous
conductivity extraction, foil calibration, distributed 2D rough surface or
magnetic hysteresis model is provided.

## Verification

Tests independently generate the rational real/imaginary sphere response,
recover a three-population synthetic model (0.2/1.2/4 µm, area ratios 0.7/2/1.5,
58 MS/m, 1 MHz–100 GHz), compare ratios at 1e-8 and predictions at 1e-10,
and check one through four populations against exhaustive nonnegative active
sets and a separate SciPy BVLS optimizer. The two numerical optimizers share
SciPy primitives; the exhaustive active sets and analytical response are
separate checks. Tests retain incompatible samples, zero populations, weight
scaling, rank deficiency, input immutability and failed optimization/KKT gates.
No mesh or exterior boundary is solved in fitting. Geometry/skin-depth and
convergence requirements still apply when using the fitted law in a line.

[한국어](../../locales/ko/pages/packages/sipi/roughness_fit.md)

## Save and replay a fitting request

`HurayFitDocument` uses `sipi.roughness-fit/1`. Its nine required fields are
`schema`, `frequency_hz`, `resistance_ohms_per_square`,
`reactance_ohms_per_square`, `radii_m`, `conductivity`,
`relative_permeability`, `weights`, and `max_error_ratio`. Defaults are expanded
into explicit numeric values and weights when constructing a document; saved
JSON cannot omit fields or use null weights. Parsing and normalization perform
input validation without SVD, optimization or a field solve.

```python
import numpy as np
from sipi.conductor import surface_impedance
from sipi.roughness import CausalHuray
from sipi.roughness_fit_document import HurayFitDocument
from sipi.execution import normalize_saved, execute_saved

frequency = np.geomspace(1e6, 1e11, 41)
samples = surface_impedance(frequency, conductivity=58e6,
    roughness=CausalHuray([.2e-6, 1.2e-6, 4e-6], [.7, 2., 1.5]))
doc = HurayFitDocument(frequency, resistance=samples.real, reactance=samples.imag,
    radii_m=[.2e-6, 1.2e-6, 4e-6], conductivity=58e6, max_error_ratio=1e-8)
text = doc.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=len(frequency))
assert output['status'] == 'complete' and output['result']['accepted']
```

The common execution budget must cover every input frequency before fitting.
A completed but incompatible candidate still has execution `status='complete'`
and result `accepted=False`; these fields have different meanings. Rank,
conditioning, optimization and input errors propagate without a fabricated
result. Duplicate/unknown keys, nonfinite numbers and incompatible versions
are rejected. Fit results use the existing `causal-huray` model object for
transmission-line v2 or later; transmission-line v1 retains its older RMS
contract. The fitting document does not itself perform a geometry solve or
change any line mesh/validity gate.
