# 두 순방향 임피던스의 동시 조건 수율 평가

[English](../../../../../packages/sipi/panel_pair_yield.md) ·
[두 양의 공차 평가](panel_pair_study.md)

`PanelForwardPairYieldDocument`는 **같은 표본에서 두 임피던스 조건을 함께**
평가합니다. 완료된 행의 실수 차동·공통 순방향 임피던스가 모두 포함 한계를 만족해야
pass입니다. 어느 한 조건이라도 벗어나면 하나의 공동 사건이 fail입니다. 두 응답의
상관을 유지하며 각 조건의 통과 비율을 곱하지 않습니다.

엄격한 `sipi.panel-forward-pair-yield/1`의 루트 키는 `schema`, `study`,
`acceptance`, `confidence`, `minimum_yield`입니다. `study`는 완전한
`sipi.panel-forward-pair-study/1` 입력입니다. iid `uniform`, `normal` 표본만
허용하며 정규 표본의 한 행 안에서 변수 간 상관은 허용합니다. sweep/corners를
iid 수율 실험으로 취급하지 않습니다.

`acceptance`에는 `differential_forward_impedance_real`,
`common_forward_impedance_real`만 있으며 각각 Ω 단위 `minimum`, `maximum`을
가집니다. 한쪽 한계는 null일 수 있지만 각 양에 하나 이상은 필요합니다. 한계는
유한한 0 이상의 수이고 minimum≤maximum이어야 합니다. 계산이 완료된 임피던스는
여전히 양수여야 합니다. confidence는 부동소수점 정밀도에서 엄격히 0과 1 사이,
minimum_yield는 null 또는 [0,1]의 확률입니다. bool은 수치 한계가 아닙니다.

## 예제

작은 완전도체 예제이며 폭의 iid 표본 4개, 고정 seed와 예시 한계를 사용합니다.
네 표본이 모두 두 조건을 만족해도 95% 신뢰수준에서 수율 하한 90%를 입증할 수는
없습니다. 길이는 m, 한계는 Ω입니다.

```python
import json
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_pair_yield import PanelForwardPairYieldDocument
from sipi.execution import normalize_saved, execute_saved

study = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.3e-3, gap=.2e-3, substrate_height=.5e-3, eps_r=4.,
         thickness=35e-6, air_height=2e-3, box_width=6e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='width', lower=.28e-3, upper=.32e-3)]))
paired = PanelForwardPairStudyDocument(study, conductor={'kind': 'perfect'})
document = PanelForwardPairYieldDocument(paired, acceptance={
    'differential_forward_impedance_real': dict(minimum=90., maximum=140.),
    'common_forward_impedance_real': dict(minimum=40., maximum=80.)},
    confidence=.95, minimum_yield=.9)
text = document.dumps()
assert normalize_saved(text) == text
assert PanelForwardPairYieldDocument.loads(text).dumps() == text
output = execute_saved(text, max_evaluations=4)
assert output['status'] == 'complete'
assert output['input'] == document.to_dict()
assert output['result']['count'] == 4 and output['result']['unresolved'] == 0
assert output['result']['goal_status'] in ('fail', 'undetermined')
json.dumps(output, allow_nan=False)
```

## 미확정 행과 신뢰구간

paired study가 생성 표본을 한 번씩 시도합니다. 추출 또는 진단 실패는 쌍 전체를
unresolved로 만들며 parameters·재료 평가·입력 생성 실패도 같습니다. 원래 행과
표본 벡터, 가능한 입력·오류를 결과와 분모에 모두 보존합니다. 실패 표본을 빼거나
대체하거나 응답을 추정해 채우지 않습니다.

계획 표본 n개, 확정 통과 p개, 미확정 u개이면 가능한 표본 통과 비율은
[p/n,(p+u)/n]입니다. 신뢰구간은 미확정 표본의 모든 가능한 판정에 대한 equal-tailed
Clopper–Pearson 구간을 감쌉니다. 하한은 p개 성공, 상한은 p+u개 성공으로 계산합니다.
하나의 공동 Bernoulli 사건이므로 두 임피던스의 독립을 가정하거나 개별 구간을
곱하지 않습니다. 전부 미확정이면 [0,1]입니다.

`goal_status`는 신뢰 하한이 minimum_yield 이상이면 pass, 상한이 목표보다 낮으면
fail, 나머지는 undetermined입니다. 목표를 주지 않으면 not-requested입니다.
실행 완료 여부는 별도입니다. 미확정 행이 있으면 공통 실행은 incomplete입니다.
최소 수율을 0으로 요청해 goal_status가 pass인 자명한 경우에도 같습니다.
행 오류는 result에 있고 최상위 error는 null입니다. 잘못된 요청, 미지원 진단,
과도한 입력 크기, 부족한 예산은 장 계산 전에 예외로 거부합니다.
취소·격리·시간/메모리 제한은 호출자가 관리합니다.

직접 `assess_panel_pair_yield(result, acceptance=..., ...)` API는 기존 paired
study를 장 재계산 없이 평가합니다. 원래 schema·iid 종류·개수·변수 순서,
정확히 재생한 표본 벡터·행 index·완료/미확정 상태를 검사합니다. 이 구조 검사는
수동으로 만든 장 결과의 진위를 입증하지 않습니다. 결과는 원래 study와 변경할 수
없는 한계를 보존합니다. to_dict()에는 두 양·표본 모델·판정·개수·구간·행이 담기며
원시 장 객체는 직접 Python study를 통해 접근합니다.

## 범위와 근거

고정된 기하·재료 표본 분포와 한계에 대한 유한 iid 추론입니다. 메시·솔버 오차,
재료 모델·제조 분포의 불확실성, 실측 생산 수율, 연속 대역, 적응적으로 후보를
선택한 뒤의 추론은 포함하지 않습니다. paired study의 장 모델 제한과 유한 수렴
검증 범위도 그대로 적용됩니다.

독립 시험은 유한 binomial tail을 역산하고 SciPy exact binomial 구간과 대조하며,
끝점 성공 개수와 작은 미확정 집합의 모든 완성 경우를 검사합니다. 같은 개별
통과율을 가지면서 공동 통과 개수가 다른 예도 포함합니다. 실제 uniform 기하
표본은 balanced 2N 고유공간, 상관 균일 복소 재료 표본은 특성 행렬 해석식과 대조한
뒤 공동 판정과 신뢰구간을 독립 산출합니다. 실측 정확도·브라우저/Worker 연결·
Windows 수락을 뜻하지 않습니다.
