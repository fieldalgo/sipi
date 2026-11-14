# 코팅 패널 쌍 선로 목표 저장

`PanelForwardPairDesignDocument.from_study(...)`는 명시적으로
`sipi.panel-forward-pair-design/2`를 만듭니다. 순서 있는 두 입력 변수,
고정 코팅 도체, 두 실수 임피던스 목표와 별도의 패널 설정을 저장합니다.
line/7과 panel-line/2만 구성하며 코팅 FEM 역산을 선택하지 않습니다.
기존 `ForwardPairDesignDocument`를 받는 생성자는 버전 1 계약과 정규화 입력을 유지합니다.

버전 2의 키는 `schema`, `study`, `conductor`, `targets_ohm`,
`tolerances_ohm`, `initial`, `max_evaluations`, `panel`로 한정하며
중첩 `design` 키는 없습니다. study 버전 3·4는 `z_diff_forward`, 양수인
단일 재료 평가 주파수, 정확히 두 변수의 corners sampling을 사용합니다.
각 변수의 양수 하한은 상한보다 작아야 합니다. 고정 pitch·고정 적층 높이·
재료 변수는 원래 study 규칙을 유지하고 예비 준정적 study를 풀지 않습니다.
탐색 중 금속 코팅은 고정합니다.

목표와 허용차의 키는 `differential_forward_impedance_real`과
`common_forward_impedance_real`입니다. 전체 복소 특성 행렬의 Re(Zdd)·Re(Zcc)에
대한 양수 Ω 값입니다. `initial`은 null(중간점) 또는 변수 순서·단위에 맞는
범위 안의 두 값입니다. 모든 길이는 m입니다.

예제는 이전에 검증한 점에서 시작해 실제 네 전계 평가를 수행합니다.
목표와 다른 점에서 탐색하려면 저장 문서에 `initial=[.7e-3,.35e-3]`를 쓰고
저장 문서와 공통 실행의 `max_evaluations`를 모두 64로 설정합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_goal_document import PanelForwardPairDesignDocument
from sipi.execution import execute_saved, normalize_saved

study = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3,
         substrate_height=.5e-3, eps_r=4., tan_delta=.02,
         left_thickness=35e-6, right_thickness=50e-6,
         box_width=.024, air_height=.010),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.4e-3, upper=.9e-3),
        dict(name='gap', lower=.2e-3, upper=.6e-3)]))
metal = dict(kind='layered', conductivity=58e6, relative_permeability=1.,
    coatings=[dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
              dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])
quantities = ('differential_forward_impedance_real', 'common_forward_impedance_real')
doc = PanelForwardPairDesignDocument.from_study(study,
    conductor=dict(kind='surface-boundaries', conductors=dict(positive=metal, negative=metal),
                   reference=metal, ground_thickness=35e-6),
    targets=dict(zip(quantities, [110., 40.])),
    tolerances=dict(zip(quantities, [.25, .125])),
    initial=[.0006073049209836395, .0004082505417130786], max_evaluations=4)
text = doc.dumps()
assert doc.to_dict()['schema'] == 'sipi.panel-forward-pair-design/2'
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=4)
assert output['status'] == 'complete'
assert len(output['result']['refinements']) == 3
```

정규화는 전계 계산 없이 명목·초기점(또는 중간점)·네 모서리 입력과 각각의
체적·패널·동시 세분 입력을 검사합니다. 금속·잔여 코어·표피 깊이·경계·패널
자원 제한을 유지하며 범위 내부 전체의 유효성을 증명하지 않습니다.
중간 후보의 실패는 실패한 시도로 남기고 자동 수리·재샘플링하지 않습니다.

저장 예산은 4~10000의 정수이며 호출자가 더 작은 예산을 주면 계산 전에
거부합니다. 기존 역산은 세 번의 실제 세분 평가를 예약하고 모든 목표 및
별도의 0.5% 세분 조건을 요구합니다. 실패 시 실제 시도 수, 완료 이력,
실패 입력과 단계를 보존하며 부분 성공으로 처리하지 않습니다.

`goal_input`은 두 버전 모두에서 정규화된 입력·목표 설정의 복사본을 반환하고
`panel_options`도 복사본입니다. 기존 `design` 속성은 버전 1 전용이며 버전 2는
TypeError를 발생시켜 기존 FEM 설계 문서로 암묵 변환되는 것을 막습니다.
정확한 저장·재실행에는 `dumps`/`loads`를 사용합니다.

회귀시험은 코팅 비대칭 예제를 목표 밖에서 실제 탐색하고, 직접 API와 공통
실행에서 정확히 같은 전계 입력을 재생합니다. 독립 코팅 전달·전체 특성·비영
길이 네트워크 검사는 [직접 코팅 역산](layered_panel_goal.md)과 같습니다.
그 외곽 검사는 별도이며 저장 wrapper가 자동으로 추가하지 않습니다.
작은 상호 저항·유한 영역·실측 정확도 한계는 유지하므로 대각 목표의 성공으로
이 정확도 문제들까지 해결됐다고 해석하지 않습니다.

[기존 목표 저장](panel_pair_goal_document.md) · [English](../../../../../packages/sipi/layered_panel_goal_document.md)
