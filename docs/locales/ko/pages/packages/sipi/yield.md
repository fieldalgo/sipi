# 명시적 공차 분포에 대한 임피던스 수율

[English](../../../../../packages/sipi/yield.md)

`sipi.yield_assessment`는 기존 무작위 임피던스 공차 시험의 모든 행을 Ω 단위의
허용 범위와 대조합니다. **지정한 분포와 수치 모델**에서 조건을 만족할 확률이며
실제 공장 수율은 아닙니다. `uniform`, `normal` 시험만 허용합니다. 스윕과 코너
검사는 유용하지만 독립·동일 분포(iid) 수율 표본으로 취급하지 않습니다.

```python
import json
from sipi.study import ImpedanceStudyDocument
from sipi.yield_assessment import ImpedanceYieldDocument
from sipi.execution import normalize_saved, execute_saved

study = ImpedanceStudyDocument("microstrip",
    dict(width=1e-3, substrate_height=.5e-3, thickness=35e-6, eps_r=4.,
         air_height=2e-3, box_width=6e-3), quantity="z0",
    sampling=dict(kind="uniform", count=4, seed=17,
        variables=[dict(name="width", lower=.95e-3, upper=1.05e-3)]),
    mesh=dict(edge_size=20e-6, far_size=.2e-3, grade=.2))
document = ImpedanceYieldDocument(study, minimum=45., maximum=55.,
                                  confidence=.95, minimum_yield=.9)
text = normalize_saved(document.dumps())
report = execute_saved(text, max_evaluations=4)
assert report["result"]["count"] == 4
assert len(report["result"]["rows"]) == 4
json.dumps(report, allow_nan=False)
```

위의 작은 표본·메시는 인터페이스 예시이며 생산 수락 시험이 아닙니다.
`document.analyze()`는 원래 `ImpedanceStudy`를 보존한 `YieldAssessment`를
반환합니다. `assess_impedance_yield(study_result, ...)`는 이미 계산한 결과를
재계산 없이 평가합니다. 기하·재료·실패를 보존합니다. 직접 만든 결과 객체만으로
지정 분포나 솔버로 결과를 얻었다는 사실을 입증하지는 않습니다.

## 집계, 실패, 신뢰구간

전체 계획 표본 수를 N, 허용 범위 안의 수를 P, 밖의 수를 F, 기하/솔버 문제로
판정할 수 없는 수를 U라 하면 `N=P+F+U`입니다. 실패 행을 제외·재추출하거나
임피던스를 만들어 넣지 않습니다. 표본 합격 비율 범위는 `[P/N, (P+U)/N]`이고
U=0일 때만 단일 값입니다. 잘못된 기하와 솔버 실패 모두 여기서는 미판정입니다.
제조 불가능 자체를 불합격 기준으로 쓰려면 별도의 모델에서 명시해야 합니다.

중앙 신뢰수준 c의 양쪽 꼬리는 각각 `(1-c)/2`입니다. U개의 가능한 모든 판정에
대한 **Clopper–Pearson 정확 이항 신뢰구간**을 포함하는 범위를 반환합니다.
하한은 N개 중 P개 합격의 하한, 상한은 P+U개 합격의 상한입니다. 합격 0개 하한은
정확히 0, 전부 합격의 상한은 1입니다. 예를 들어 100/100 합격의 95% 신뢰 하한은
약 0.9638입니다. 표본 100% 합격이 모집단 수율 100%의 증명은 아닙니다.

표본 수를 사전에 정한 단일 설계의 구간입니다. 정규분포 한 행 안의 변수 상관은
허용하지만 행끼리는 같은 분포에서 독립적으로 추출해야 합니다. 신뢰수준은 이런
시험을 반복할 때의 포함률이며, 얻어진 구간에 고정된 참 수율이 들어갈 확률이라는
뜻은 아닙니다. 메시·재료 피팅 오차, 분포 매개변수의 불확실성, 표본 선택 편향,
결과를 본 뒤의 조기 중단은 포함하지 않습니다. 여러 설계를 탐색해 하나를 고르면
다중 비교 제어가 별도로 필요하며 이 단일 설계 API가 이를 제공하지 않습니다.

선택적 `minimum_yield`는 [0,1] 범위입니다. `goal_status`는 다음과 같습니다.

- 신뢰 하한이 목표 이상이면 `pass`;
- 신뢰 상한이 목표보다 작으면 `fail`;
- 나머지는 `undetermined`, 목표가 null이면 `not-requested`.

기본 신뢰수준은 .95이며 실수 표현 정밀도에서 0과 1 사이여야 합니다. 임피던스
한계는 유한한 0 이상의 수 또는 null입니다. 적어도 한쪽이 있어야 하고
`minimum <= maximum`이어야 합니다. 경계값은 숨은 여유 없이 포함합니다.

## 저장 계약과 공통 실행

`sipi.impedance-yield/1`은 정확히 `schema`, `study`, `minimum`, `maximum`,
`confidence`, `minimum_yield`를 갖습니다. `study`는 기존 임피던스 공차 버전
1–4이며 기하/재료 변수 바인딩과 원래 seed·표본 수·상관을 보존합니다. 미지원
버전·추가 키·중복 JSON 키·비유한 값·일부만 남기거나 순서를 바꾼 결과는 거부합니다.
읽을 때 필드를 풀지 않습니다. 입력과 내보낸 사전은 분리된 사본입니다.

`execute_saved`는 필드 계산 전에 중첩 공차 전체의 평가 예산을 검사합니다.
결과에는 물리량·Ω 한계·분포·P/F/U·표본 비율 범위·신뢰구간·목표 판정과 모든
행의 값·매개변수·기하·재료·오류가 남습니다. U>0이면 `status="incomplete"`,
계산이 모두 끝났으면 수율 목표의 통과 여부와 별개로 `status="complete"`입니다.
구간 방식과 지정 분포의 평가라는 범위를 명시합니다. 미완 계산을 낙관적인 수율로
바꾸지 않습니다.

작은 N에서 독립 이항 다항식 합과 이분법으로 구간을 `1e-12`에 검증하고 SciPy의
정확 이항 구간 API와도 비교합니다. 끝점·대칭·신뢰수준/표본 수 변화·미판정 범위·
엄격 JSON·예산·실제 FEM 공차 재생을 검사합니다. 기존 필드·메시 기준을 유지하며
실행 의존성이나 새로운 물리 정확도 주장은 추가하지 않습니다.
