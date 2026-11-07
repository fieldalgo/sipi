# Sampled network-band limits

[한국어](../../locales/ko/pages/packages/sipi/band.md) · [Saved execution](execution.md)

`NetworkBandDocument` saves a network source and explicit constraints on
`abs(S[output_port, input_port])`. This evaluates insertion, reflection, crosstalk
or mode conversion in the network's power-wave basis. It uses the existing port
reference loads at all other ports; it is not a loaded-voltage crosstalk ratio.

```python
from sipi.band import NetworkBandDocument, db_to_magnitude
from sipi.lumped import LumpedNetworkDocument

network = dict(kind='lumped-network',
    document=LumpedNetworkDocument([0, 1e8, 2e8], resistance=25).to_dict())
plan = NetworkBandDocument(network, limits=[dict(
    name='insertion', input_port='near', output_port='far',
    frequency_hz=[0, 2e8], minimum=db_to_magnitude(-3), maximum=None)])
result = NetworkBandDocument.loads(plan.dumps()).analyze()
assert result.passed
assert result.to_dict()['coverage'] == 'frequency-samples-only'
```

The exact `sipi.network-band/1` fields are `schema`, `network`, `basis` and
`limits`. Source kinds are `rlgc`, `touchstone`, `lumped-network`,
`transmission-line`, `volume-line`, `network-assembly` and `network-transform`,
with their existing strict documents and physical gates. Parsing never solves a
geometry field; RLGC/lumped validators may perform small network calculations.

`basis` is `single-ended` or an explicit `mixed-mode` conversion. The latter
requires four single-ended ports ordered near+/near-/far+/far-, with equal
reference impedance. Output order is d_near,d_far,c_near,c_far, with differential
reference 2Z and common reference Z/2. Port identities are not inferred from their
spelling; the caller must supply that physical order.

There are 1–64 limits, each with exactly these fields:

| Field | Meaning |
|---|---|
| `name` | Unique nonempty single-line label |
| `input_port`, `output_port` | Existing port names in the selected basis |
| `frequency_hz` | Two increasing endpoints both present exactly in the input grid |
| `minimum`, `maximum` | Inclusive finite nonnegative linear magnitude bounds, or null |

At least one bound is required. When both exist, minimum <= maximum. Bounds may
exceed one for externally supplied networks; an assessment does not declare that
network passive. Frequencies between the endpoints are selected from the stored
grid, including both endpoints. There is no interpolation, extrapolation, grid
refinement, continuous-band extremum or guarantee about unsampled resonances.

`db_to_magnitude(dB)` returns 10**(dB/20), rejecting nonfinite and unrepresentable
limits. For insertion loss <=3 dB use **minimum** 10**(-3/20); for return loss
>=20 dB use **maximum** 10**(-20/20) on reflection. Likewise use a maximum for
crosstalk or mode conversion. These are amplitude dB of power-normalized S;
unequal references do not turn them into raw voltage ratios.

Every check retains all selected frequencies, magnitudes and signed margins.
Margin is magnitude-minimum, maximum-magnitude, or their minimum when both bounds
exist. It passes only when every margin is nonnegative, with no hidden tolerance.
`failed_indices` uses the selected frequency array; `worst_index` selects its
first minimum-margin entry, including ties. Exact zero is a finite magnitude,
not a clipped dB floor. Overall margin is the minimum over all checks. Zero-bound
comparisons can fail on numerical roundoff; set an explicit appropriate bound.

`assess_band(LineNetwork, limits)` performs the same checks on an existing network.
Saved results also retain the original input and optional field extraction. The
shared execution adapter exports finite check data and reference/basis metadata.
Its `status='complete'` means calculation completed; `result.passed` separately
reports whether requirements were met. A violated limit is not a solver failure.

Validation uses a 25-ohm series resistor (S21=.8, S11=.2 at 50 ohms), directed
nonreciprocal examples, zero and exact-boundary cases, explicit mixed-mode ports,
assembly/transform/Touchstone replay and actual field-source composition. A
matched distortionless line is compared with exp(-alpha*length) and independent
scikit-rf 2.2.0 `DefinedGammaZ0` (1e-10 gates). No new field discretization is added;
existing mesh/domain, material and measurement validity limits still apply.

```sh
python -m pytest -q tests/sipi/test_band.py tests/sipi/test_network_document.py tests/sipi/test_network_assembly.py tests/sipi/test_lumped_network.py tests/sipi/test_execution.py
```

[Line-length boundary design](length_design.md) applies several sampled limits to a uniform RLGC length bracket.
