# 유한주파수 쌍 선로의 고정 후보 비교

[English](../../../../../packages/sipi/sampled_panel_pair_selection.md) ·
[공동 판정](sampled_panel_pair_yield.md) · [단일주파수 후보](panel_pair_selection.md)

`SampledPanelForwardPairSelectionDocument`는 미리 정한 1..32개 후보를 같은
주파수별 한계로 비교합니다. 후보마다 고유 이름, 유한한 0 이상 비용과
전체 `SampledPanelForwardPairStudyDocument`를 제공합니다. iid uniform/normal만
허용하며 모든 후보의 양의 주파수 배열은 순서와 값이 정확히 같아야 합니다.
표본 수, 명시한 기하·재료·메시·패널 설정은 달라도 되며 결과에 남습니다.
보간이나 한계 자동 확장은 없고 비용은 호출자가 정한 동일 단위를 씁니다.

저장 형식 `sipi.sampled-panel-forward-pair-selection/1`의 키는 정확히
`schema`, `candidates`, `cost_unit`, `acceptance`, `confidence`, `minimum_yield`입니다.
후보 키는 `name`, `cost`, `study`이며 공동 판정의 두 이름별 minimum/maximum
배열을 사용합니다. 각 양·주파수마다 하나 이상의 포함 한계가 필요합니다.
목표 확률 [0,1]은 필수입니다. 후보·판정 조건·분포는 관측 전에 고정해야 하며
관측 후 고른 후보군이나 적응 탐색의 신뢰구간이 아닙니다.

제조 표본 하나가 Bernoulli 시행 하나입니다. 두 임피던스가 모든 지정
주파수의 조건을 함께 만족해야 통과하고, 주파수 수로 표본 분모를 늘리지 않습니다.
후보 K개에는 기존 보수적 exact-float Bonferroni로 후보별 신뢰수준을 최소
1-(1-confidence)/K로 배분합니다. 후보 수에만 배분하며 주파수·양의 수를 추가
인자로 곱하지 않습니다. 후보 사이의 표본·seed·의존성 공유는 허용하지만 각
후보 내부 행은 그 명시 분포의 iid 표본이어야 합니다. 1에 가까워 배분을
표현할 수 없는 신뢰수준은 거부합니다.

실패한 전주파수 행은 원분모에 unresolved로 남고 Clopper-Pearson 구간은
가능한 모든 미해결 판정을 포함합니다. 하한이 목표 이상인 후보만 인증하며
상한이 목표 미만이면 실패, 나머지는 미정입니다. 인증된 후보 중 최저 비용을
고르고 정확한 비용 동률은 원순서로 결정합니다. 더 싼 미해결 후보도 실제로는
가능할 수 있습니다. 연속·전역 최적이라는 뜻이 아닙니다. 인증 후보가 없으면
모두 실패한 none-certified와 아직 미정인 undetermined를 구분합니다.

호출자의 2..10000 평가 예산은 중복·실패를 포함한 전체 후보의 계획 제조 행을
셉니다. 예산 확인과 모든 후보의 표본 생성이 장 계산보다 먼저 끝나야 합니다.
그 뒤 모든 행·후보를 실행하며 조기 선택·재표집을 하지 않습니다. 전체 입력,
공통 주파수, 원행·실패 원인·구간·비용·선택을 보존합니다. 하나라도 계산 실패면
다른 후보가 선택되어도 실행은 incomplete입니다. 목표 0도 실패를 숨기지 않습니다.
모든 장 계산이 성공하면 인증 후보가 없어도 실행 자체는 complete입니다.

## 재현 예제

같은 study를 두 번 사용해 후보 사이 의존성을 보여 줍니다. 각 후보의
4개가 모두 통과하면 후보 신뢰수준 .975의 하한은 약 .334370이므로 예시 목표
.3을 넘습니다. 복제 후보를 합쳐 각 구간의 표본을 8개로 세지 않습니다.
비용이 낮은 두 번째 후보가 선택됩니다.

```python
from sipi.dielectric import DebyeDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.sampled_panel_pair_selection import SampledPanelForwardPairSelectionDocument
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
request = SampledPanelForwardPairSelectionDocument(
    [dict(name="first", cost=2.0, study=study.to_dict()),
     dict(name="second", cost=1.0, study=study.to_dict())],
    cost_unit="relative-cost",
    acceptance={q: dict(minimum=[0.0] * 3, maximum=[1000.0] * 3) for q in quantities},
    confidence=0.95, minimum_yield=0.3)
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=8)
assert output["status"] == "complete"
assert output["result"]["evaluations"] == 8
assert output["result"]["candidate_confidence"] == 0.975
assert output["result"]["selected"] == dict(index=1, name="second", cost=1.0)
assert all(c["assessment"]["passed"] == 4 for c in output["result"]["candidates"])
```

## 검증과 범위

1..32개 후보의 정확한 오차 배분, 독립 binomial 꼬리, 상관된 중복 후보,
주파수 수를 늘려도 같은 표본 분모·구간, 서로 다른 주파수에서의 실패,
전체 후보 사전 확인, 비용 동률·더 싼 미해결 후보·원실패 단계 보존을 검사합니다.
기존 단일주파수 저장 계약은 유지합니다.

실제 고정 후보군은 비균일 기하 4개와 상관된 균일 Debye 재료 4개를 .5/1/2GHz에서
평가합니다. 이 별도 선택 사례의 한계는 두 양 모두 0..1000Ω, 비용2/1,
신뢰수준 .95, 목표 .3으로 고정했습니다. 두 후보가 동시 신뢰하한을 통과해
재료 후보가 선택됩니다. balanced2N·해석 재료 행렬은 1e-10, 독립 binomial
구간은 1e-12 이내에서 일치합니다. 재료식은 C0를 공유하므로 독립 기하 해가
아닙니다. 이 넓은 한계의 예제로 공동 판정의 좁은 한계 실패를 바꾸지 않습니다.

이 통계 연결은 새 장 수렴 인증, 연속 대역 보장, 실측 생산 수율이나 모델
오차 보장을 추가하지 않습니다. 기존 장·표본 사례의 한정된 검증 범위를
따릅니다. 브라우저/Worker/단일EXE 연결과 다른 플랫폼 검증도 별도입니다.
