# 공통 전류 고정 후보의 동시 신뢰구간과 선택

[English](../../../../../packages/sipi/common_forward_yield_design.md) | **한국어**

명시적 `sipi.yield-design/3`는 `line-quantity-study/3`의 고정 후보와
공통 전류 순방향 Re(Zcc)를 지원합니다. 모든 후보는 동일한 물리량과 양의
주파수를 사용해야 합니다. 버전 1·2의 입력 계약과 생성자 기본값 1은 유지합니다.
물리량 및 미확정 행의 의미는 [표본 분석](common_forward_line_study.md)과
[iid 구간](common_forward_line_yield.md) 계약을 따릅니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.yield_design import YieldDesignDocument
from sipi.execution import normalize_saved, execute_saved

def metal(conductivity, rms):
    return dict(conductivity=conductivity, relative_permeability=1.,
                roughness=dict(kind='hammerstad', rms_m=rms))

def candidate(name, cost, low, high):
    nominal = (low+high)/2
    source = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
        dict(left_width=nominal, right_width=.5e-3, gap=.95e-3-(nominal+.5e-3)/2,
            substrate_height=.5e-3, eps_r=4., tan_delta=.02,
            left_thickness=35e-6, right_thickness=50e-6,
            box_width=24e-3, air_height=10e-3),
        quantity='z_diff_forward', frequency=1e9, materials={}, fixed_pitch_m=.95e-3,
        mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
        sampling=dict(kind='uniform', count=2, seed=17,
            variables=[dict(name='left_width', lower=low, upper=high)]))
    study = LineQuantityStudyDocument(source, schema='sipi.line-quantity-study/3',
        quantity='common_forward_impedance_real',
        conductor=dict(kind='surface-boundaries',
            conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
            reference=metal(58e6, 0.), ground_thickness=35e-6))
    return dict(name=name, cost=cost, study=study.to_dict())

doc = YieldDesignDocument([
    candidate('narrower', 2., .6e-3, .7e-3),
    candidate('wider', 1., .7e-3, .8e-3)],
    schema='sipi.yield-design/3', cost_unit='relative fabrication cost',
    minimum=38., maximum=41., confidence=.9, minimum_yield=.1)
assert normalize_saved(doc.dumps()) == doc.dumps()
result = doc.analyze(max_evaluations=4)
assert result.status == 'selected' and result.selected_index == 1
assert result.unresolved == 0
```

루트 키는 `schema`, `candidates`, `cost_unit`, `minimum`, `maximum`,
`confidence`, `minimum_yield` 일곱 개입니다. 후보는 1–32개이고 각각
`name`, `cost`, `study`만 포함합니다. 이름은 고유해야 하며 비용은 호출자가
정한 한 단위의 유한한 비음수입니다. 기하나 제조 과정에서 비용을 자동 추정하지
않습니다. 모든 후보는 표본을 계산하기 전에 고정합니다.

요청한 전체 신뢰수준을 Bonferroni 방식으로 보수적으로 배분하고, 각 후보는
기존 Clopper–Pearson 미확정 분류 구간을 사용합니다. 부동소수점 반올림이
정확한 전체 실패 확률 예산을 초과하지 않게 합니다. 각 후보의 행은 명시한
uniform·normal 분포의 iid 표본이어야 하지만 후보들끼리는 같은 seed를
사용할 수 있고 서로 독립일 필요는 없습니다.

```python
from fractions import Fraction
import json
import numpy as np
assert (1-Fraction(result.candidate_confidence))*2 <= 1-Fraction(.9)
for item in result.candidates:
    assert item.assessment.passed == 2
    low = ((1-result.candidate_confidence)/2)**.5
    np.testing.assert_allclose(item.assessment.confidence_interval, [low, 1.], rtol=0., atol=1e-12)
    assert [row.index for row in item.assessment.study.rows] == [0, 1]
report = execute_saved(doc.dumps(), max_evaluations=4)
assert report['status'] == 'complete' and report['result'] == result.to_dict()
assert report['result']['unit'] == 'ohm'
assert report['result']['evaluations'] == 4
assert report['result']['selected'] == dict(index=1, name='wider', cost=1.)
json.dumps(report, allow_nan=False)
```

모든 후보와 원래 표본 행을 보존합니다. 미확정 행은 분모·실패 단계·가능한
입력을 유지하며, 저렴하지만 미확정인 후보를 불가능하다고 처리하지 않습니다.
인증된 후보 중 비용이 가장 낮은 것을 선택하고 동률이면 입력 순서를 따릅니다.
인증 후보가 없을 때 모두 목표 미달로 인증되어야 `none-certified`이고,
그 외는 `undetermined`입니다. 후보가 선택되더라도 미확정 행 때문에 바깥
실행 보고서는 incomplete일 수 있습니다.

전체 계획 표본 수를 첫 field 계산 전에 확인합니다. 분포의 표본 생성 자체가
불가능하면 부분 선택 결과 없이 예외를 내며, 개별 솔버 실패는 미확정 행으로
남깁니다. 개수 제한은 메모리·실행 시간 제한이 아닙니다. 적응 최적화나 연속·
전역 최적해 보장이 아니며, 신뢰구간은 명시한 분포를 가정하고 수치·재료 적합·
모델 오차를 포함하지 않습니다.

후보 수 1/2/3/7/32와 다섯 신뢰수준에서 정확한 유리수 전체 예산, 독립 유한
이항합 역산 1e-12, 미확정·동률·선택 없음·이전 출력·엄격 입력을 검증합니다.
실제 비대칭 두 후보의 각 두 폭 표본은 직접 평가와 저장 보고서를 정확히
재생하고 전체 RLGC를 1e-10 이내로 비교합니다. 이전 저장 입력 96종의
정규형을 유지합니다. 앞선 세 폭의 메시·유한 외곽 검증을 보존하지만 모든
확률 표본의 수렴을 보장하지 않습니다. 실측 생산 수율·새 플랫폼·배포 수락을
뜻하지 않습니다.
