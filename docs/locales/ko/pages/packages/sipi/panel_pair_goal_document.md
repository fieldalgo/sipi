# 명시 패널 전류를 사용하는 저장형 두 목표 역산

[English](../../../../../packages/sipi/panel_pair_goal_document.md) ·
[직접 패널 역산](panel_pair_goal.md) · [패널 선로](panel_line.md) ·
[두 양의 공차 평가](panel_pair_study.md)

`PanelForwardPairDesignDocument`는 명시 패널 전류 역산을
`sipi.panel-forward-pair-design/1`로 저장합니다. 최상위 키는 `schema`, `design`, `panel`
세 개입니다. `design`은 정규화한 `sipi.forward-pair-design/1` 입력이며, `panel`에는
`panels_per_edge`, `ground_modes`, `interpolation_degree`만 넣습니다. 기존 저장 목표의
계산 방법은 바꾸지 않습니다.

내부 study/3 또는 /4는 순서 있는 양수 범위의 기하·재료 변수 두 개, 양수 주파수 하나,
도체 법칙, 이름 있는 Re(Zdd)/Re(Zcc) 목표와 절대 Ω 허용치를 제공합니다. 고정 피치와
지원하는 재료 leaf 규칙을 유지합니다. 내부 시도 예산은 4~10000이어야 합니다.
패널 선로의 bottom-ground/open-top/open-sides와 도체 제한도 적용합니다.
다른 단면을 지원하지 않으면 거부하며 다른 솔버로 자동 전환하지 않습니다.

## 예제

이미 수락한 점에서 시작해도 원입력·체적만 세분·패널만 세분·동시 세분의 네 평가를
수행합니다. 목표 밖에서 탐색하려면 `initial=[.7e-3,.35e-3]`와 저장/호출자 예산 64를
사용합니다. 길이는 m, 목표와 허용치는 Ω입니다.

```python
import json
from sipi.study import ImpedanceStudyDocument
from sipi.pair_line_goal_document import ForwardPairDesignDocument
from sipi.panel_pair_goal_document import PanelForwardPairDesignDocument
from sipi.execution import normalize_saved, execute_saved

study = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3,
         substrate_height=.5e-3, eps_r=4., tan_delta=.02,
         left_thickness=35e-6, right_thickness=50e-6,
         air_height=10e-3, box_width=24e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.4e-3, upper=.9e-3),
        dict(name='gap', lower=.2e-3, upper=.6e-3)]))
def metal(conductivity, rms):
    return dict(conductivity=conductivity, relative_permeability=1.,
                roughness=dict(kind='hammerstad', rms_m=rms))
conductor = dict(kind='surface-boundaries',
    conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
    reference=metal(58e6, 0.), ground_thickness=35e-6)
quantities = ['differential_forward_impedance_real', 'common_forward_impedance_real']
design = ForwardPairDesignDocument(study, conductor=conductor,
    targets=dict(zip(quantities, [110., 40.])),
    tolerances=dict(zip(quantities, [.25, .125])),
    initial=[.000603169086210573, .00040941866189257275], max_evaluations=4)
document = PanelForwardPairDesignDocument(design,
    panels_per_edge=32, ground_modes=512, interpolation_degree=10)
text = document.dumps()
assert normalize_saved(text) == text
assert PanelForwardPairDesignDocument.loads(text).dumps() == text
output = execute_saved(text, max_evaluations=4)
assert output['status'] == 'complete'
assert output['input'] == document.to_dict()
assert output['result']['evaluations'] == 4
assert [row['stage'] for row in output['result']['refinements']] == [
    'volume-refinement', 'panel-refinement', 'joint-refinement']
json.dumps(output, allow_nan=False)
```

## 입력 검사·실행·실패

파싱은 깊은 복사본을 정규화하고 nominal·initial/중간값·네 corner 입력과 각각의
후속 세분 문서 세 개를 검사합니다. 메시나 예비 임피던스 study는 실행하지 않습니다.
이 유한 검사는 전체 탐색 영역의 유효성·skin-depth 조건·field 수렴·후속 계산 성공을
보장하지 않습니다. 입력 복구·재표본·fallback은 없습니다. 미지/누락/중복 키,
미지원 버전과 비유한 JSON 값을 거부합니다. 접근자는 독립 문서와 설정을 반환합니다.

`solve()`는 명시 패널 역산을 직접 호출하고 전체 Python 결과를 반환합니다.
선택/세분 panel-line snapshot과 원래 예외를 보존합니다. `execute_saved()`는 전체 저장
요청, 이력·매개변수·물리량·잔차·세 세분 결과를 JSON 호환 보고서로 반환합니다.
Python factory를 직렬화하지 않습니다. 원시 행렬/field 객체는 직접 결과에서 접근하며,
요약 보고서에 포함되었다고 가정하지 않습니다.

호출자의 실행 예산은 저장 예산 이상이어야 하며 자동으로 줄이지 않습니다.
미지원 최상위 diagnostics와 입력 크기 초과는 계산 전에 거부합니다. 제어/파싱 오류는
예외를 냅니다. 목표 계산 실패는 `status='failed'`, `result=null`과 원래 단계·원인 종류·
시도 수·실패 매개변수/입력·완료 이력을 반환합니다. 배열과 tuple은 JSON 배열로 바뀌며
실패 행을 삭제하거나 성공으로 바꾸지 않습니다. 취소·프로세스 격리·시간/메모리 한도는
호출자가 담당합니다.

## 검증 범위

독립 모드 회로 해로 저장/직접 계산의 일치와 변수 순서를 확인합니다. 고정 피치·재료 leaf,
field-free 입력 검사, 자원/전달 한도와 각 탐색·세분 단계의 실패를 시험합니다.
수락한 비균일·비대칭 사례의 기록 연구에서는 네 정규화 선로 입력을 보존하고 이전 직접
계산의 목표값과 정확히 일치했습니다. 제품 시험은 저장 요청을 실제 실행하며 네 전체 특성
행렬을 독립 balanced 2N 고유공간과 1e-10 이내로 대조합니다. 추출 RLGC를 재사용하므로
독립 기하 추출이나 실측 검증은 아닙니다.

공통 registry에는 이 명시 스키마가 추가되고 기존 정규화 입력과 계산 방법은 그대로입니다.
이것은 엔진 실행 계약이며 새 브라우저 폼·Worker/EXE 연결·연속대역 수락·외곽 오차 상한·
전역 최적화·실측 정확도 완료를 뜻하지 않습니다.
