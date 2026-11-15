# 모서리 해상도를 명시한 FEM 계산량 표본

`CornerFEMShapeLineQuantityStudyDocument`의 스키마는
`sipi.corner-fem-shape-line-quantity-study/1`이며 키는 `schema`, `study`,
`corner_size`입니다. 내포된 [기존 FEM 공차 문서](fem_shape_study.md)의
기하·재료 표본, 계산량, 금속과 양의 주파수를 유지합니다. 모서리 목표는
미터 단위의 유한 양수이고 공칭 입력의 해석된 edge 크기 이하여야 합니다.
정규화는 장을 풀지 않습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi import (FEMShapeLineQuantityStudyDocument,
                  CornerFEMShapeLineQuantityStudyDocument)
from sipi.execution import normalize_saved

source = ImpedanceStudyDocument('stripline',
    dict(width=.0004, plane_spacing=.002, eps_r=4.,
         thickness=.00005, box_width=.008),
    quantity='z0', frequency=2e9, materials={},
    mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1),
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='width', lower=.00039, upper=.00041)]))
metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness=dict(kind='smooth'))
study = FEMShapeLineQuantityStudyDocument(source,
    conductors=dict(signal=metal), reference=metal,
    ground_thickness=35e-6, quantity='impedance_real')
saved = CornerFEMShapeLineQuantityStudyDocument(study, corner_size=2.5e-6)
assert normalize_saved(saved.dumps()) == saved.dumps()
# result = saved.analyze(max_evaluations=2)
```

각 표본은 같은 모서리 목표, 길이 0, 포트 기준 50Ω인 명시적
[모서리 FEM 선로](corner_fem_line.md)를 만듭니다. 기하·재료를 행마다
다시 평가하고 서로 다른 기하의 메시를 공유하지 않습니다. 기존 전류,
표피 깊이와 진단 검사를 유지하며 각 행 입력에서 모서리 목표도 다시
검사합니다.

계산량의 의미는 기존과 같습니다. 단일 선로의 실수 임피던스·감쇠,
쌍 선로의 Ic=0·Id=0 구동에 대한 실수 차동·공통 순방향 임피던스입니다.
쌍 계산량을 독립 전파 모드로 해석하지 않습니다. 호스트 예산은 선로
시도 횟수이며 각 선로 안에는 여러 장 풀이가 있습니다. 모든 요청 행의
개수를 장 풀이 전에 검사합니다.

표본 순서, 중복, 입력 사본, 재료 평가, 완료·부분 전류 근거를 보존합니다.
실패한 행이 있어도 다음 행을 시도하며 모든 행이 성공해야 기술 통계를
계산합니다. 값을 자르거나 다시 추출하거나 가중하지 않으며 생산 수율을
의미하지 않습니다. 공통 실행기·요청·기록·프로젝트에서도 이 계약을
유지합니다. 기록을 다시 열어도 풀지 않으며 모서리 설정 변경 시 현재
결과 연결을 해제하고 과거 기록을 보존합니다.

검증은 기존 사례와 같은 모서리 목표의 실제 장, 더 작은 모서리의 단일·쌍
표본, 독립 특성량, 재료 감쇠와 실패 저장을 포함합니다. 이 유한 관측은
모든 표본의 메시·외곽 수렴, 작은 상호 손실 정확도, 연속 매개변수 범위나
새로운 플랫폼을 인증하지 않습니다. 기존 공차 스키마는 내부 source mesh의
corner 키를 계속 거부합니다.

[English](../../../../../packages/sipi/corner_fem_study.md)
