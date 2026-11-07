# 단일 재료 파라미터 임피던스 역산

[English](../../../../../packages/sipi/material_goals.md) · [재료 공차](material_variables.md) · [기하 역산](design.md)

`ImpedanceDesignDocument`에 `material_variables`를 지정하면
`sipi.impedance-design/3`으로 저장합니다. 버전 2의 필드에 이 객체를 추가하며,
`variable`과 같은 별칭의 바인딩 하나만 허용합니다.
[공차 바인딩 계약](material_variables.md)에 따라 재료 모델의 숫자 항목 하나를
선택합니다. 이 저장 문서에서 기하와 관측 주파수는 고정입니다.
버전 1·2의 기존 의미는 유지합니다.

```python
from sipi.design_document import ImpedanceDesignDocument
from sipi.dielectric import ConstantDielectric
import json

plan = ImpedanceDesignDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, eps_r=1),
    variable='dk', bounds=[2, 8], target=50, tolerance=.25,
    frequency=1e8, materials={'dielectric': ConstantDielectric(4)},
    material_variables={'dk': dict(region='dielectric', path=['eps_r'])},
    mesh=dict(edge_size=2e-6, far_size=.125e-3, grade=.15))
result = ImpedanceDesignDocument.loads(plan.dumps()).solve()
assert abs(result.residual) <= .25
assert abs(result.refined_residual) <= .25
actual = json.loads(result.material_evaluation_json)
assert actual['materials']['dielectric']['parameters']['eps_r'] == result.parameter
```

반환 파라미터의 단위는 선택한 모델 항목의 상대유전율·Hz 등입니다. 탐색 경계는
유한한 양수이고 오름차순이어야 합니다. 공차 분석에서 0이나 음수가 허용되는
손실·각도라도 이 역산 API는 그런 구간을 검색하지 않습니다. nominal과 양 끝점,
계산하는 모든 중간 모델을 검증합니다. 모델이 유효하다는 사실은 실측 유효범위나
제조 가능성, 실제 구매 가능한 재료의 존재를 보장하지 않습니다.

목표는 `Re(C)`와 진공 외부 인덕턴스로 계산한 실수 준정적 임피던스입니다.
복소 특성 임피던스·감쇠·대역·수율·다변수 최적화 목표가 아닙니다. 균일 매질의
손실탄젠트 변경은 이 실수 목표에 영향을 주지 않을 수 있습니다. 양 끝점이
목표를 둘러싸지 못하면 재료 fitting 결과로 제시하지 않고 거부합니다.

기존 이분법 계약을 유지합니다. 양 끝점을 계산하고 한 번의 계산 예산을
세분화 검사에 남깁니다. edge size·far size·grading을 절반으로 줄인 메시와
요청 메시에서 모두 목표를 만족해야 합니다. 외곽 경계는 고정이므로 별도로
검사해야 합니다. 비단조 모델에 해의 유일성이나 전역 최적성을 보장하지 않습니다.

`result.document`는 선택 기하와 요청 메시를, `material_evaluation_json`은
nominal이 아닌 **선택된 재료**의 스냅샷을 보존합니다. 직접 재생에는 둘 다
저장하고, 전체 탐색 재실행에는 design JSON을 보존합니다. 공통 저장 실행은
버전 3의 선택 재료·잔차·세분화·완료된 탐색 이력을 보존합니다. 기존
`GoalSeekError`와 예산 제한도 유지하며, 잘못된 factory나 모델 입력은 성공한
목표로 바꾸지 않고 검증 오류를 전달합니다.

Python API의 `seek_impedance(..., frequency=f,
material_factory=models_at_parameter)`는 파라미터별 영역→재료 모델 맵을
반환하는 콜백을 받습니다. `materials`와 동시에 사용하지 못합니다. 기하
factory에도 같은 파라미터가 전달되므로 Python 사용자는 기하·재료의 연동을
명시적으로 정의할 수 있습니다. 이는 기하가 고정인 저장 문서와 다릅니다.
각 탐색 시 재료 입력을 즉시 복사하고 선택 스냅샷을 세분화에서도 재사용하며
콜백을 다시 부르지 않습니다. 재현성을 위해 콜백은 결정적이어야 합니다.
JSON에는 함수나 코드를 저장하지 않습니다.

독립 Cohn 식으로 균일 stripline의 목표 유전율을 역산하여 1% 이내인지 확인하고,
요청·세분 메시 잔차를 각각 0.25Ω 이내로 검사합니다. Debye 극점은 독립 실수
유전율 식의 목표와 1.5% 이내로 비교하고, 1µm/grade 0.1 요청 메시에서
요청·세분 잔차를 0.1Ω 이내로 검사합니다. 0.25Ω 정지는 극점 기준에 부족하여
극점 허용오차를 넓히지 않고 목표 잔차를 더 엄격하게 정했습니다. 선택 재료의 직접 재생 차이는 상대
1e−10 이하이어야 합니다. 끝점 선택·세분화 시 재료 스냅샷 보존·추가 콜백 없음,
엄격한 입력·미bracket·예산 소진·공통 실행을 기존 설계/재료 회귀와 함께 검사합니다.
필드 솔버 자체는 변경하지 않습니다. 기존 workbench 빌드에는 새 스키마가
자동 반영되지 않습니다.

```sh
python -m pytest -q tests/sipi/test_material_goals.py tests/sipi/test_material_variables.py tests/sipi/test_material_impedance.py tests/sipi/test_design_documents.py tests/sipi/test_impedance_design_document.py tests/sipi/test_execution.py
```
