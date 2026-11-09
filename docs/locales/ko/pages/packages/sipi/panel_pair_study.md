# 명시 패널 전류를 사용하는 두 순방향 임피던스 공차 평가

[English](../../../../../packages/sipi/panel_pair_study.md) ·
[패널 선로](panel_line.md) · [두 목표 저장](panel_pair_goal_document.md) ·
[동시 조건 수율](panel_pair_yield.md)

`PanelForwardPairStudyDocument`는 **표본마다 한 번 추출**하여
`differential_forward_impedance_real`, `common_forward_impedance_real`을
이 순서로 계산합니다. 단위는 Ω이며, 전체 복소 순방향 특성 행렬을 전력 쌍대
혼합 좌표로 바꾼 Ic=0 인가의 Re(Zdd), Id=0 인가의 Re(Zcc)입니다.
비대칭 결합 항을 보존하며, 두 인가를 독립 전파 모드로 간주하지 않습니다.

엄격한 `sipi.panel-forward-pair-study/1`의 루트 키는 `schema`, `study`,
`conductor`, `panel` 네 개입니다. 내부 paired impedance study/3 또는 /4는
고정 양의 주파수, 순서 있는 기하·재료 변수, 표본 및 제약을 제공합니다.
`z_diff_forward`는 입력 계약만 선택하며 기존 준정적 study를 실행하지 않습니다.
고정 피치, 재료 수치 잎, seed와 기존 sweep/corners/uniform/상관 정규 표본의 의미,
기존 study 형식의 계산 방법은 유지됩니다.

`panel`에는 `panels_per_edge`, `ground_modes`, `interpolation_degree`만 둡니다.
양의 두께 직사각형, 하부 접지·상부/측면 개방, 지원 도체 법칙 등
[패널 선로의 제한](panel_line.md)을 적용합니다. 미지원 입력을 다른 방법으로
바꾸지 않습니다. 요청하지 않은 추가 세분의 입력 허용 여부는 요구하지 않습니다.

## 예제

길이는 m입니다. 아래 완전도체 예제는 폭 세 지점을 공통 저장 엔진 경로로 평가합니다.

```python
import json
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.execution import normalize_saved, execute_saved

study = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.3e-3, gap=.2e-3, substrate_height=.5e-3, eps_r=4.,
         thickness=35e-6, air_height=2e-3, box_width=6e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='width', lower=.28e-3, upper=.32e-3)]))
document = PanelForwardPairStudyDocument(study, conductor={'kind': 'perfect'},
    panels_per_edge=32, ground_modes=512, interpolation_degree=10)
text = document.dumps()
assert normalize_saved(text) == text
assert PanelForwardPairStudyDocument.loads(text).dumps() == text
output = execute_saved(text, max_evaluations=3)
assert output['status'] == 'complete'
assert output['input'] == document.to_dict()
assert output['result']['count'] == 3 and output['result']['failed'] == 0
assert output['result']['quantities'] == [
    'differential_forward_impedance_real', 'common_forward_impedance_real']
assert all(len(row['values_ohm']) == 2 for row in output['result']['rows'])
json.dumps(output, allow_nan=False)
```

## 시도·실패·통계

파싱은 깊은 복사와 명목 입력 정규화만 수행하며 장 계산을 하지 않습니다.
모든 표본의 유효성을 보장하지는 않습니다. `samples()`는 원래 순서의 표본을
돌려줍니다. `analyze(max_evaluations=128)`는 모든 표본을 생성하고 개수를 정수
예산 2..10000과 비교한 뒤 계산합니다. 생성 오류·overflow 또는 부족한 예산은
장 계산 전에 거부합니다. 이후 중복과 실패 뒤의 표본까지 모든 행을 순서대로
한 번씩 시도합니다. 입력 자르기·재추출·행 삭제·재가중을 하지 않습니다.

각 행에는 index, 표본값, 해석된 parameters, material evaluation, 가능할 때
전체 panel-line 입력을 남깁니다. 실패 시 원래 예외 형식·메시지와
`parameters`, `materials`, `input`, `extraction`, `diagnostic` 중 단계를
보존합니다. 추출 후 진단이 실패해도 이미 얻은 결과는 Python 행에 남습니다.
두 임피던스는 함께 성공하거나 실패하며 실패 쌍의 `values_ohm`은 null입니다.

Python 결과에는 `rows`, `failed`, `variable_names`, `input_json`과 변경할 수
없는 중첩 `summary` 매핑이 있습니다. `to_dict()`는 원시 장·행렬 객체를 제외한
JSON 호환 보고서를 만듭니다. 모든 행이 성공할 때만 각 양의 최솟값·최댓값·평균·
표본 표준편차·선형 보간 5/95 백분위수를 제공합니다. **한 행이라도 실패하면 전체
summary는 null**입니다. 기술 통계이며 수율 신뢰구간이나 극값 보장이 아닙니다.
기존 단일 양의 yield 입력은 이 두 양의 요청을 묵시적으로 받아들이지 않습니다.

공통 실행은 전체 요청을 보존하며 실패 행이 있으면 `status='incomplete'`를
반환합니다. 원래 행 오류는 `result`에 있고 최상위 `error`는 null입니다.
잘못된 요청은 예외를 내므로 미완 표본 집합과 구분됩니다. 입력 크기, 미지원 진단,
평가 한도는 계산 전에 검사합니다. 취소·프로세스 격리·시간/메모리 한도는 호출자 책임입니다.

## 수치 범위와 검증

해석된 명목 메시·패널 설정을 모든 행에 고정합니다. 같은 기하 메시를 재사용하거나
각 표본의 자동 수렴 검사를 제공하지는 않습니다. 추출 후에도 같은 주파수·신호 순서·
진단 좌표계를 유지해야 합니다. 비유한 값, 잘못된 행렬 크기, 양수가 아닌 임피던스는
쌍 전체의 실패입니다. 기존 기하·자원·표피 깊이 기준은 그대로입니다.

시험은 독립 결합 모드 해석식과 기술 통계를 대조하고 상관 표본의 잘못된 기하,
중복·재료 변수·고정 피치를 확인합니다. 서로 다른 금속을 쓰는 비대칭 기하 4개
표본은 독립 balanced 2N 고유공간 계산과 상대 1e-10 이내로 대조합니다. 같은
RLGC를 재사용하므로 독립 기하 해석은 아닙니다. 완전 상관 균일 복소 유전체 표본
4개는 C=eps*C0, R=0 및 전체 특성 행렬 해석식
`sqrt(mu0*epsilon0/complex_eps)*inverse(C0)`를 상대 1e-10 이내로 만족합니다.

별도 기하 연구의 첫·마지막 corner에서는 메시·패널 동시 세분과 외곽 영역 3개도
검사했습니다. 두 양의 상대 변화 .005 이내 및 연속 외곽 절대 변화 감소를 통과했습니다.
이 유한 검증은 모든 표본이나 연속 변수 영역의 보장이 아닙니다. 연속 대역·생산 수율·
전역 최적화·실측 정확도·브라우저/Worker 연결·Windows 수락은 별도입니다.
