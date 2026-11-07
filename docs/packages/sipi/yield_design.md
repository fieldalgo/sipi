# Select from fixed designs under a yield constraint

[한국어](../../locales/ko/pages/packages/sipi/yield_design.md)

`sipi.yield_design.YieldDesignDocument` evaluates a **predeclared finite set** of
random impedance studies and chooses the lowest-cost member whose conservative
yield lower bound meets the target. It reuses [iid yield assessment](yield.md)
and the existing geometry/material studies. It does not generate designs, infer
fabrication costs or claim a continuous/global optimum.

```python
import json
from sipi.study import ImpedanceStudyDocument
from sipi.yield_design import YieldDesignDocument
from sipi.execution import execute_saved, normalize_saved

candidates = []
for name, dk, cost in [("material-a", 4., 1.), ("material-b", 3.5, 1.2)]:
    study = ImpedanceStudyDocument("microstrip",
        dict(width=1e-3, substrate_height=.5e-3, thickness=35e-6, eps_r=dk,
             air_height=2e-3, box_width=6e-3), quantity="z0",
        sampling=dict(kind="uniform", count=2, seed=17,
            variables=[dict(name="width", lower=.95e-3, upper=1.05e-3)]),
        mesh=dict(edge_size=20e-6, far_size=.2e-3, grade=.2))
    candidates.append(dict(name=name, cost=cost, study=study.to_dict()))
document = YieldDesignDocument(candidates, cost_unit="relative fabrication cost",
    minimum=45., maximum=55., minimum_yield=.9, confidence=.95)
report = execute_saved(normalize_saved(document.dumps()), max_evaluations=4)
assert report["result"]["evaluations"] == 4
assert len(report["result"]["candidates"]) == 2
assert report["result"]["selected"] is None  # too few samples to certify 90%
json.dumps(report, allow_nan=False)
```

This tiny example checks the interface; it is not a production acceptance study.
The objective is a finite nonnegative number supplied by the caller in the
explicit common `cost_unit`. There is no expression evaluator. A candidate may
change several nominal dimensions/materials and use joint correlated normal
variables within a row. All candidates must use the same impedance quantity and
inclusive ohm limits. Their sample counts, seeds and stated distributions can
differ and remain visible. Common random seeds are allowed.

## Simultaneous confidence and selection

For M fixed candidates and requested family confidence c, each candidate uses
confidence `1-(1-c)/M`. The implementation rounds **upward when necessary** so
the exact stored floating-point failure budgets sum to no more than `1-c`;
it rejects a level that rounds to 1. Each candidate retains its Clopper–Pearson
interval envelope over unresolved labels. By the Bonferroni union bound, the
probability that any interval misses its stated-distribution yield is at most
`1-c`. Candidate independence is not required. Rows within each candidate must
be iid, and the set, distributions, counts and criteria must be fixed before
looking at outcomes. Coverage does not extend to repeated adaptive searches,
optional stopping or choosing a new candidate set after inspecting this report.

Only candidates with `confidence_interval[0] >= minimum_yield` are eligible.
Among them, minimum cost wins; equal costs use the original input order. The
result means **lowest-cost certified member of this fixed set**. A cheaper
`undetermined` candidate might actually meet the target; it is retained, not
declared infeasible. All rows and errors from every candidate remain in output.
No failed solve is discarded, rerun or replaced by a made-up impedance.

Result `status` is `selected` when an eligible member exists, `none-certified`
when every candidate's upper bound is below the target, and `undetermined`
otherwise. `selected` contains index/name/cost or is null. The common execution
status is separate: any unresolved field row gives `incomplete`, even if a
candidate is selected; otherwise calculations are `complete`, even if no design
is selected. A target of zero is vacuously satisfied, including unresolved rows;
one cannot certify yield 1 with a finite positive-confidence sample.

## Saved input, budgets and evidence

`sipi.yield-design/1` has exactly `schema`, `candidates`, `cost_unit`, `minimum`,
`maximum`, `minimum_yield` and `confidence`. `candidates` is a list of 1–32
entries, each exactly `name`, `cost`, `study`; names are unique. Names and unit
are nonempty single-line strings, at most 128 characters with no surrounding
whitespace/control characters. `study` is a strict impedance-study/1–4 dictionary
with `uniform` or `normal` sampling. The acceptance/confidence rules match
[yield assessment](yield.md); the target is mandatory. Unknown/duplicate keys,
mixed impedance quantities, nonfinite values and unsupported versions reject.
Inputs and exported dictionaries are detached snapshots. Parsing solves no field.

`document.analyze(max_evaluations=...)` returns `YieldDesignResult`; common
`execute_saved` serializes it. Both check the **sum of all planned samples**
against the integer 2–10000 evaluation budget before the first solve. No early
stopping occurs after finding an eligible candidate. Input snapshots, original
study inputs, per-candidate statistics/geometry/material/errors, requested and
actual per-candidate confidence, cost and selection are retained. Memory/time
and cancellation limits still belong to the caller.

Tests use independent finite binomial tail inversion (`1e-12`) and exact count
enumeration/union bounds, rational checks of floating failure budgets, identical
correlated candidates, ties, cheaper unresolved designs, target endpoints,
whole-set budget rejection, strict/detached JSON, material provenance and actual
FEM replay. This is a statistical composition of existing field studies; it
introduces no field discretization. Existing mesh/material/model errors are not
included in the confidence interval. It is not measured manufacturing yield,
a new physical-accuracy validation, or an application/platform acceptance.
