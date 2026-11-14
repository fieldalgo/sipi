# 검증된 FEM 전류의 기하·재료 표본 계산

`FEMShapeLineQuantityStudyDocument`는 각 표본에 FEM 형상 전류 선로를 명시적으로
선택합니다. 내부 `ImpedanceStudyDocument`의 study/3 또는 /4가 기하, 고정 양의
주파수, 유전체 모델, 제약과 표본 생성을 정합니다. `z0` 또는 `z_diff_forward`는
단일·쌍 입력을 선택하는 표시이며 원 준정적 계산은 실행하지 않습니다.

```python
from sipi import FEMShapeLineQuantityStudyDocument
from sipi.study import ImpedanceStudyDocument

source = ImpedanceStudyDocument(
    'stripline', dict(width=.0004, plane_spacing=.002, eps_r=4.,
                     thickness=.00005, box_width=.008),
    quantity='z0', frequency=2e9, materials={},
    mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1),
    sampling=dict(kind='sweep', count=2,
                  variables=[dict(name='width', lower=.00039, upper=.00041)]))
metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness=dict(kind='smooth'))
document = FEMShapeLineQuantityStudyDocument(
    source, conductors={'signal': metal}, reference=metal,
    ground_thickness=35e-6, quantity='impedance_real')
assert FEMShapeLineQuantityStudyDocument.loads(document.dumps()).dumps() == document.dumps()
# result = document.analyze(max_evaluations=2)
# print(result.to_dict())
```

엄격한 6키 `sipi.fem-shape-line-quantity-study/1`은 `schema`, `study`,
`conductors`, `reference`, `ground_thickness_m`, `quantity`를 저장합니다.
각 신호에 하나의 고정된 전체 경계 금속 법칙을 적용하고 모든 접지는 공통 기준
금속을 사용합니다. 층상 금속·유한 코어·표피 깊이 조건은
[저장 FEM 선로](fem_shape_line.md)의 규칙을 유지합니다. 금속 변수는 표본화하지
않으며 기하·유전체 숫자 leaf는 내부 study의 기존 규칙을 따릅니다. 알 수 없는 키,
중복 JSON 키와 비유한 입력 숫자는 거절합니다.

단일 입력은 `impedance_real`(Re Zc, Ω) 또는 `attenuation`(Re gamma, Np/m)을
선택합니다. 쌍 입력은 `differential_forward_impedance_real`(Ic=0의 Re Zdd) 또는
`common_forward_impedance_real`(Id=0의 Re Zcc)을 선택합니다. 비대칭 결합을 보존하며
독립 전파 모드라고 가정하지 않습니다. 각 표본은 길이 0, 네트워크 기준 50Ω인
선로를 구성합니다. 이 특성량은 포트 기준 임피던스에 의존하지 않습니다.

전계 계산 전에 모든 표본을 생성하고 예산을 확인합니다. 예산은 실패·중복을 포함한
선로 시도 횟수이며 내부 커패시턴스·속도 풀이 횟수가 아닙니다. 표본의 순서와 값을
유지하고 실패 뒤의 표본도 시도합니다. 잘라내기·거절 표본화·재추출·중복 제거·가중치
변경은 하지 않습니다. KeyboardInterrupt/SystemExit는 전파합니다. 명목 입력에서
정규화한 메시 설정을 재사용하지만 바뀐 기하는 다시 메시합니다. 자동 메시·외곽 수렴
인증을 제공하지 않습니다.

각 행은 파라미터·재료 평가·정규화 선로 입력·실패 단계/종류/메시지와 추출된 결과를
보존합니다. 완료된 전류에는 원 gradient 근거와 형상 미분 표본이 모두 들어갑니다.
선로의 typed 실패는 완료 또는 부분 전류를 `cause_details`에 보존하고, 이후 진단
실패는 완료 전류를 `current_solver`에 남깁니다. 없는 전류 자료를 만들어 채우지
않습니다. 실패 자료의 비유한 문자열 표시는 저장 선로 계약을 따릅니다.

모든 행이 성공해야 최소·최대·평균·표본 표준편차·선형 p05/p95를 제공합니다. 실패한
행은 값이 없고 전체 요약을 생략합니다. 상관 표본·corner·유한 sweep은 생산 수율을
입증하지 않으며 신뢰구간도 제공하지 않습니다. 공통 실행은 실패 행이 있는 study를
`incomplete`로 기록하고 행을 보존합니다. 실행 기록과 프로젝트는 재계산 없이 영수증을
저장합니다.

실제 단일·쌍 폭 표본과 유전체 손실 표본을 독립 스칼라 제곱근·행렬 제곱근의 특성량,
메시 세분, 정상·부분 실패 기록과 대조합니다. 전달만 검사할 때 재사용한 추출 결과는
새 전계 계산과 구분합니다. 전류 미분 기준·원 gradient flux·금속 조건은 바꾸지
않습니다. 전체 회귀·플랫폼 지원·실행시간 상한·실측 정확도는 별도 근거가 필요합니다.
기존 저장 study 기본값은 그대로입니다.

[English](../../../../../packages/sipi/fem_shape_study.md)
