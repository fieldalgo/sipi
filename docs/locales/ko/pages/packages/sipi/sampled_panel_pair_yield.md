# 유한 주파수 전체의 공동 iid 판정

[English](../../../../../packages/sipi/sampled_panel_pair_yield.md) ·
[다주파수 제조 표본](sampled_panel_pair_study.md) · [단일 주파수 공동 판정](panel_pair_yield.md)

`assess_sampled_panel_pair_yield`는 제조 iid 표본 하나를 Bernoulli 시행 하나로 봅니다.
완료 행은 모든 지정 주파수에서 두 임피던스가 각각의 포함 한계를 만족해야 통과합니다.
하나라도 벗어나면 실패, 주파수 묶음 계산 실패는 미해결입니다. 주파수와 두 양 사이의
상관을 허용하며 주파수 수로 제조 표본 수를 늘리거나 주변 통과 비율을 곱하지 않습니다.

`SampledPanelForwardPairYieldDocument`의 저장 형식은
`sipi.sampled-panel-forward-pair-yield/1`이며 키는 정확히 `schema`, `study`,
`acceptance`, `confidence`, `minimum_yield`입니다. 중첩 문서는 iid uniform 또는
normal 방식의 다주파수 두 양 표본입니다. sweep·corners는 거부하고 행 안의 매개변수
상관은 기존 의미를 유지합니다. 양의 주파수 배열과 첫 기준 주파수 규칙도 그대로입니다.

acceptance는 `differential_forward_impedance_real`, `common_forward_impedance_real`
두 이름만 받습니다. 각각의 `minimum`, `maximum`은 주파수마다 하나씩 있는 ohm
배열입니다. 원소는 null 또는 유한한 0 이상의 값이며, 각 양·주파수마다 적어도 한쪽
한계가 있어야 하고 하한이 상한보다 높으면 안 됩니다. 스칼라 자동 확장은 없습니다.
평가 자료를 보기 전에 판정 기준과 표본 설계를 고정해야 합니다.

이 하나의 공동 사건에 대해 양쪽 꼬리를 같은 크기로 둔 Clopper-Pearson 구간을
계산합니다. 미해결 행이 있으면 그 라벨의 가능한 모든 조합을 감싸는 구간을 반환하며
원래 분모를 유지합니다. 사전에 정한 하나의 사건이므로 주파수별 다중 보정은 하지
않습니다. 주파수별 확률을 따로 보고하거나 기준·모델·설계를 자료를 본 뒤 선택하는
경우의 동시 보장은 아닙니다. 표본 비율 범위와 신뢰구간은 구분해서 제공합니다.

`minimum_yield`가 있으면 신뢰 하한이 목표 이상일 때 `pass`, 신뢰 상한이 목표보다
낮을 때 `fail`, 나머지는 `undetermined`입니다. 목표가 없으면 `not-requested`입니다.
선언한 iid 분포와 고정 수치 사건에 대한 판정이며, 솔버·재료·메시·분포 모델의 불확실성,
실측 생산 수율 또는 연속 주파수 대역을 보증하지 않습니다.

평가는 저장 원본을 재구성하고 정확한 주파수·변수·행 순서, 모든 원래 표본 벡터,
양의 유한 `(N, 2)` 완료 값 또는 일관된 미해결 행을 검사합니다. 평가 자체는 장 계산을
하지 않습니다. 구조 검사가 수동으로 만든 물리 결과의 진위를 인증하지는 않습니다.
불변 결과는 모든 행, 이름별 한계 배열, 라벨, 개수, 표본 비율 범위와 신뢰구간을
보존하며 원래 입력과 실패 원인도 유지합니다.

`execute_saved()`는 호출자 행 예산을 사용합니다. 모든 장 계산이 성공하면 수율
목표 실패와 관계없이 실행은 `complete`입니다. 미해결 행이 하나라도 있으면 실행은
`incomplete`이며 수율 판정과 독립적입니다. 예를 들어 목표가 0이면 goal은 통과해도
실행은 불완전할 수 있습니다. 잘못된 입력·비iid 방식·전체 표본 생성·예산 오류는
장 계산 전에 예외를 냅니다.

## 재현 가능한 재료 예제

다음 네 상관 균일 재료 표본은 설명용으로 넓게 정한 한계를 모두 만족합니다.
그래도 95% 신뢰수준에서 공동 확률 0.9를 확인하기에는 부족합니다. 하한은 약
0.397635입니다. 이는 선언한 모의 분포이며 실측 제조 모집단이 아닙니다.

```python
from sipi.dielectric import DebyeDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.sampled_panel_pair_yield import SampledPanelForwardPairYieldDocument
from sipi.execution import normalize_saved, execute_saved

frequencies = [0.5e9, 1e9, 2e9]
material = DebyeDielectric(3.0, (0.7,), (1e9,))
source = ImpedanceStudyDocument("coupled_microstrip",
    dict(width=0.3e-3, gap=0.2e-3, substrate_height=0.5e-3, eps_r=4,
         thickness=35e-6, air_height=2e-3, box_width=6e-3),
    quantity="z_diff_forward", frequency=frequencies[0],
    materials=dict(substrate=material, air=material),
    mesh=dict(edge_size=10e-6, far_size=0.2e-3, grade=0.1),
    material_variables={
        "strength_substrate": dict(region="substrate", path=["strengths", 0]),
        "strength_air": dict(region="air", path=["strengths", 0])},
    sampling=dict(kind="normal", count=4, seed=3,
        correlation=[[1.0, 1.0], [1.0, 1.0]], variables=[
            dict(name="strength_substrate", mean=0.7, std=0.05),
            dict(name="strength_air", mean=0.7, std=0.05)]))
study = SampledPanelForwardPairStudyDocument(source,
    conductor=dict(kind="perfect"), frequencies=frequencies)
quantities = ("differential_forward_impedance_real", "common_forward_impedance_real")
request = SampledPanelForwardPairYieldDocument(study,
    acceptance={q: dict(minimum=[0.0] * 3, maximum=[1000.0] * 3) for q in quantities},
    confidence=0.95, minimum_yield=0.9)
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=4)
assert output["status"] == "complete"
assert output["result"]["count"] == output["result"]["passed"] == 4
assert output["result"]["goal_status"] == "undetermined"
assert output["result"]["confidence_interval"][0] < 0.9
```

## 검증과 유효 범위

독립 유한 binomial 합과 실제 SciPy exact 구간으로 일반·극단 개수를 대조합니다.
모든 미해결 라벨 완성, 서로 반대인 주파수 주변 사건, 배열을 늘려도 유지되는 제조
표본 수, 포함·비대칭·단측 한계, 잘못된 수동 행 및 실행·목표 상태 분리를 검사합니다.

고정 uniform 기하 네 표본에서 0.5/1/2 GHz마다 차동 109.5..110.5 ohm, 공통
39.9..40.1 ohm을 적용합니다. 독립 balanced 2N 특성행렬과 1e-10 이내에서 일치하고
fail/pass/fail/fail 라벨이 같습니다. 95% 구간은 약 [0.006309, 0.805880]이므로
선언한 0.9 목표는 실패합니다. 상관 균일 Debye 네 표본은 복소 구성식과 1e-10 이내로
일치하며 모두 통과해도 0.9 목표는 미확정입니다. 독립 구간 비교의 절대 허용치는 1e-12입니다.

장 계산 사례와 표본 단계 수렴 연구의 유효 범위는 제한되어 있습니다. 이 통계 계층은
새 기하·외곽 수렴 보장을 추가하지 않습니다. 브라우저·Worker·EXE 연결이나 플랫폼
지원도 뜻하지 않습니다. 이전 저장 형식과 단일 주파수 추론 계약은 유지합니다.
