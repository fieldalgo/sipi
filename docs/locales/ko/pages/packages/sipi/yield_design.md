# 수율 조건으로 고정 설계 후보 선택

[English](../../../../../packages/sipi/yield_design.md)

`sipi.yield_design.YieldDesignDocument`는 **결과를 보기 전에 지정한 유한 후보 집합**을
평가하고, 수율 신뢰하한이 목표 이상인 후보 중 비용이 가장 낮은 것을 선택합니다.
기존 [iid 수율 평가](yield.md)와 기하·재료 공차 study를 재사용합니다.
설계 후보나 제조 비용을 자동 생성하지 않으며 연속 공간의 전역 최적을 주장하지 않습니다.

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
assert report["result"]["selected"] is None  # 두 표본으로 수율 90% 인증 불가
json.dumps(report, allow_nan=False)
```

위 소수 표본·메시 예제는 인터페이스 확인용이며 생산 수락 시험이 아닙니다.
`cost`는 호출자가 공통 `cost_unit`으로 제공한 유한 비음수 목적값입니다.
임의 식 실행은 없습니다. 후보별 여러 공칭 치수·재료를 변경할 수 있고 정규 표본의
행 내부 변수 상관도 허용합니다. 임피던스 quantity와 양끝 포함 ohm 허용범위는
모든 후보에 공통입니다. 표본수·분포·seed는 후보마다 달라도 되며 모두 보존합니다.
후보 사이 같은 seed를 사용하는 것도 허용합니다.

## 동시 신뢰수준과 선택 의미

고정 후보 M개, 요청 family confidence c에 대해 후보별 신뢰수준은 `1-(1-c)/M`입니다.
저장된 부동소수점 값의 실패확률 예산 합이 정확히 `1-c` 이하가 되도록 필요하면
**위로 반올림**합니다. 1로 반올림되어 표현할 수 없는 수준은 거부합니다.
각 후보는 실패 label의 모든 가능성을 포함하는 Clopper–Pearson envelope를 유지합니다.
Bonferroni 합집합 상한에 의해 어느 구간이라도 명시 분포의 참 수율을 놓칠 확률은
`1-c` 이하입니다. 후보 간 독립은 필요하지 않지만 각 후보 안의 행은 iid여야 합니다.
후보·분포·표본수·판정조건을 결과 확인 전에 고정해야 합니다. 적응형 후보 추가,
유리한 결과가 나왔을 때 중단, 반복 탐색 전체에 대한 보장으로 확대할 수 없습니다.

`confidence_interval[0] >= minimum_yield`인 후보만 선택 대상입니다. 그중 최소 비용,
동점이면 입력 순서로 선택합니다. 뜻은 **고정 집합에서 수율이 인증된 후보 중 최소 비용**입니다.
더 싼 `undetermined` 후보도 실제로는 목표를 충족할 수 있으며 불가능하다고 취급하지 않습니다.
모든 후보의 모든 행과 오류를 출력에 남기며 실패를 버리거나 재표집하거나 임피던스를 만들지 않습니다.

결과 `status`는 선택 후보가 있으면 `selected`, 모든 후보의 신뢰상한이 목표보다 낮으면
`none-certified`, 그 외는 `undetermined`입니다. `selected`에는 index/name/cost 또는 null이
들어갑니다. 공통 실행 status는 별개입니다. 실패 행이 하나라도 있으면 선택되었더라도
`incomplete`; 모든 계산이 끝나면 설계 선택 여부와 무관하게 `complete`입니다.
목표 0은 실패 행이 있어도 자명하게 만족하고, 유한 표본·양의 신뢰수준으로 수율 1은 인증할 수 없습니다.

## 저장·예산·검증

`sipi.yield-design/1`은 정확히 `schema`, `candidates`, `cost_unit`, `minimum`,
`maximum`, `minimum_yield`, `confidence` 필드를 갖습니다. 후보는 1–32개 list이며
각 항목은 정확히 `name`, `cost`, `study`입니다. 이름은 중복할 수 없습니다.
이름·단위는 비어 있지 않은 최대 128자 한 줄 문자열이며 앞뒤 공백·제어문자를 거부합니다.
`study`는 uniform/normal을 쓰는 strict impedance-study/1–4 dictionary입니다.
허용범위·신뢰수준 규칙은 [수율 평가](yield.md)와 같고 목표수율은 필수입니다.
미지원 버전·알 수 없거나 중복된 키·서로 다른 quantity·비유한 수를 거부합니다.
입출력 dictionary는 분리된 snapshot이고 parsing 중 field solve는 없습니다.

`document.analyze(max_evaluations=...)`는 `YieldDesignResult`를 반환하며 공통
`execute_saved`가 이를 직렬화합니다. 첫 solve 전에 **모든 후보의 계획 표본수 합**을
정수 2–10000 예산과 비교합니다. 만족하는 후보를 찾았다고 조기 종료하지 않습니다.
입력·후보별 원래 study·통계·기하·재료·오류, 요청/실제 후보 신뢰수준, 비용·선택을 남깁니다.
메모리·시간 제한과 취소는 여전히 호출자 책임입니다.

독립 유한 binomial tail 역산 `1e-12`, 가능한 count 전개와 union bound, float 실패예산의
정확 유리수 검사, 동일/상관 후보·동점·싼 미정 후보·목표 끝점·합산예산 선검사·strict JSON과
snapshot·재료 provenance·실제 FEM replay를 검사합니다. 기존 field study의 통계적 조합이며
새 이산화는 없습니다. 메시·재료·모델 오차는 신뢰구간에 포함되지 않습니다.
실측 제조수율·새 물리 정확도·앱/플랫폼 검증 완료를 뜻하지 않습니다.
