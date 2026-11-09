# 두 임피던스 수율 조건으로 고정 후보 선택

[English](../../../../../packages/sipi/panel_pair_selection.md) ·
[동시 조건 수율](panel_pair_yield.md) · [두 양의 공차 평가](panel_pair_study.md)

`PanelForwardPairSelectionDocument`는 **사전에 정한 유한 후보 집합**을 비교합니다.
공동 수율의 신뢰 하한으로 목표를 입증한 후보 중 제공된 비용이 가장 낮은 후보를
선택합니다. [공동 판정](panel_pair_yield.md)에 따라 같은 행에서 두 임피던스 조건을
모두 만족해야 합니다. 후보끼리 또는 두 임피던스끼리 독립이라고 가정하지 않습니다.

엄격한 `sipi.panel-forward-pair-selection/1`의 루트 키는 `schema`, `candidates`,
`cost_unit`, `acceptance`, `confidence`, `minimum_yield`입니다. 공통 비용 단위,
이름 있는 두 Ω 포함 한계, 전체 후보 집합의 신뢰수준, 필수 수율 목표를 지정합니다.
한계·확률은 공동 수율 계약을 따릅니다. 0 목표도 허용하지만 자명한 확률 조건입니다.

`candidates`는 1..32개 `{name, cost, study}`의 목록입니다. 이름은 중복 없이
앞뒤 공백 없는 1..128자의 출력 가능한 한 줄 문자열입니다. 비용은 호출자가 제공한
유한한 0 이상의 수이며 별도 비용 모델·환율 계산은 없습니다. study는 iid uniform
또는 normal 표본을 가진 `sipi.panel-forward-pair-study/1` 입력입니다.
모든 후보의 양의 주파수는 같아야 합니다. 명시된 기하·재료·분포·패널 설정은
후보마다 달라도 되며 그대로 보존합니다. 입력이 같고 이름만 다른 후보도 합치지 않고
후보 집합의 신뢰수준 보정에 포함합니다.

## 예제

작은 완전도체 예제는 두 기판 높이에서 폭 표본을 네 개씩 계산합니다. 비용과 넓은
한계는 예시입니다. .3 목표는 인터페이스 설명용이며 후보당 네 표본으로 전체 95%
신뢰수준에서 수율 하한 90%를 입증할 수는 없습니다. 길이는 m, 한계는 Ω입니다.

```python
import json
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_pair_selection import PanelForwardPairSelectionDocument
from sipi.execution import normalize_saved, execute_saved

study = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.3e-3, gap=.2e-3, substrate_height=.5e-3, eps_r=4.,
         thickness=35e-6, air_height=2e-3, box_width=6e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='width', lower=.28e-3, upper=.32e-3)]))
first = PanelForwardPairStudyDocument(study, conductor={'kind': 'perfect'}).to_dict()
second = json.loads(json.dumps(first))
second['study']['parameters']['substrate_height'] = .52e-3
document = PanelForwardPairSelectionDocument([
    dict(name='first', cost=1., study=first),
    dict(name='second', cost=.8, study=second)], cost_unit='relative-cost',
    acceptance={
        'differential_forward_impedance_real': dict(minimum=90., maximum=140.),
        'common_forward_impedance_real': dict(minimum=40., maximum=80.)},
    confidence=.95, minimum_yield=.3)
text = document.dumps()
assert normalize_saved(text) == text
assert PanelForwardPairSelectionDocument.loads(text).dumps() == text
output = execute_saved(text, max_evaluations=8)
assert output['status'] == 'complete'
assert output['input'] == document.to_dict()
assert output['result']['evaluations'] == 8
assert len(output['result']['candidates']) == 2
assert output['result']['status'] in ('selected', 'none-certified', 'undetermined')
json.dumps(output, allow_nan=False)
```

## 동시 신뢰구간과 선택

고정 후보 K개와 전체 신뢰수준 c에 대해 각 공동 사건의 신뢰수준은 적어도
`1-(1-c)/K`입니다. 정확한 유리수 연산과 보수적인 float 반올림으로 후보별 오류
예산의 합이 `1-c`를 넘지 않게 합니다. 1에 가까워 표현할 수 없는 수준은 거부합니다.
한 행이 이미 하나의 AND 사건이므로 두 양에 대한 추가 2배 보정은 하지 않습니다.
각 후보에 기존 Clopper–Pearson 미확정 판정 포괄 구간을 적용합니다.

모든 후보와 행을 보존합니다. goal_status가 pass인 후보 중 제공 비용을 최소화하며
동률이면 원래 index를 따릅니다. 인증된 후보가 있으면 selected, 모두 fail이면
none-certified, 나머지는 undetermined입니다. 더 저렴한 미확정 후보가 실제로
가능할 수도 있으므로 선택 결과가 그 가능성을 배제하거나 전역·연속 최적점을
입증하지는 않습니다.

어느 후보에든 미확정 행이 있으면 공통 실행은 incomplete입니다. 인증된 후보를
선택했거나 자명한 0 목표를 준 경우에도 같습니다. 모든 계산은 성공했지만 조건을
벗어난 경우 complete 실행과 none-certified 결과가 함께 나올 수 있습니다.
행 오류는 각 후보 assessment 안에 있고 최상위 error는 null입니다.
잘못된 입력·제어값은 예외로 거부합니다.

직접 결과에는 input_json, 변경할 수 없는 candidates 튜플, candidate_confidence,
selected_index, status, unresolved가 있습니다. 각 후보에는 이름·비용·전체 공동
assessment가 남습니다. to_dict()는 두 양과 단위, 공통 한계·비용 단위,
전체/후보 신뢰수준·목표·선택된 후보와 모든 후보 입력·원래 행을 제공합니다.

## 예산·수치 범위·검증

`analyze(max_evaluations=128)`는 모든 후보의 선언된 표본 수 합계를 정수 예산
2..10000과 비교하고, 모든 후보의 표본 생성도 첫 장 계산 전에 검사합니다.
따라서 뒤 후보의 표본 생성 overflow 때문에 앞서 계산한 후보 결과를 잃지 않습니다.
유한하지만 잘못된 기하는 실제 시도에서 미확정 행으로 남깁니다.

실패·중복·이미 인증된 후보 뒤에 있는 후보까지 모두 원래 순서로 시도합니다.
재추출, 조기 중단, 적응적 후보 생성, 숨은 최적화는 없습니다. evaluations는
추출 전에 실패한 경우까지 포함한 원래 시도 행 수이며 성공한 장 계산 횟수가 아닙니다.
각 study의 명시 설정과 기하·표피 깊이·자원 기준, 제한된 수렴 검증 범위를 유지합니다.
취소·격리·시간/메모리 제한은 호출자가 관리하며 입력 크기·미지원 진단은 계산 전에 검사합니다.

시험은 지원하는 모든 후보 개수의 정확한 전체 오류 예산, 독립 binomial 구간,
동률·저가 미확정 후보·다른 표본 수·사전 overflow·전체 예산과 실패 뒤 후보 실행을
확인합니다. 별도 실제 두 후보·uniform 8표본 사례는 독립 balanced 2N 행렬과
상대 1e-10, 독립 공동 판정·exact binomial 구간과 절대 1e-12 이내로 대조합니다.
명시한 예시 .3 목표를 입증한 후보 중 더 낮은 비용의 후보를 선택합니다.

고정된 iid 모델에 대한 구간이며 실측 생산 수율·장/모델/분포 오차·적응적 선택 뒤
추론·연속 대역 보장·브라우저/Worker 연결·Windows 수락은 포함하지 않습니다.
