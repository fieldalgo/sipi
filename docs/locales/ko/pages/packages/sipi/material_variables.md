# 재료 파라미터 공차 분석

[English](../../../../../packages/sipi/material_variables.md) · [공차 분석](study.md)

`ImpedanceStudyDocument`에 `material_variables`를 주면
`sipi.impedance-study/4`로 저장합니다. 버전 3의 필수 필드에 이 객체를
추가하며, 기존 버전의 의미는 바뀌지 않습니다.

바인딩은 샘플링 별칭을 `{region, path}`에 연결합니다. 영역은 명시한 재료
오버라이드에 있어야 합니다. 경로는 해당 모델의 `parameters`에서 시작하여
기존의 유한 숫자 하나를 선택합니다. 객체 키는 문자열, 배열 인덱스는 0 이상의
정확한 정수여야 하며 불리언은 거부합니다. 별칭은 기하 인자 이름과 겹칠 수
없고 같은 재료 항목에 두 별칭을 연결할 수 없습니다. 모든 바인딩은 샘플링
변수에 포함해야 합니다. 기하·재료 변수를 합하여 1–8개까지 지원합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import DebyeDielectric

plan = ImpedanceStudyDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, eps_r=1), quantity='z0',
    frequency=1e8, materials={'dielectric': DebyeDielectric(2, [3], [1e8])},
    material_variables={'pole': dict(region='dielectric', path=['relaxation_hz', 0])},
    sampling=dict(kind='sweep', count=3,
                  variables=[dict(name='pole', lower=5e7, upper=2e8)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
restored = ImpedanceStudyDocument.loads(plan.dumps())
result = restored.analyze()
assert result.failed == 0
assert result.rows[0].material_evaluation_json is not None
```

상수 모델은 `['eps_r']`, `['tan_delta']`, Debye는 `['strengths', 0]`,
`['relaxation_hz', 0]`, 광대역 모델은 `['eps_ref']`, `['tan_delta_ref']`,
표는 `['eps_r', 0]`, 주축 모델은 `['axis1', 'parameters', 'eps_r']`,
`['angle_rad']` 같은 경로를 사용합니다. 단위는 원래 모델의 상대유전율,
무차원 손실탄젠트, Hz, rad입니다. 모델 종류·배열 길이·스키마 버전은 변경하지
못합니다. 관측 주파수는 고정이며 모델의 교정 주파수 변경과 구분합니다.

sweep/corners/uniform/correlated normal 모두 기하·재료의 동시 변동을 지원합니다.
기존 고정 피치·전체 판 간격 규칙도 유지합니다. 재료 오버라이드가 있는 경우
기존 템플릿의 `eps_r`/`tan_delta` 변수는 계속 거부합니다. 표본이 덮어써져
무시되지 않도록 재료 모델의 명시적 바인딩을 사용합니다.

생성 시 nominal과 유한 범위의 모든 모서리를 필드 계산 없이 검증합니다.
모서리 통과가 모든 중간 모델의 유효성을 보장하지 않으므로 실제 계산 행마다
표의 순서·주파수 범위, 광대역 교정, 차동 텐서 대칭 조건을 다시 검사합니다.
잘못된 정규분포 표본은 자르거나 다시 뽑지 않고 실패로 보존하며, 실패가 하나라도
있으면 요약 통계는 없습니다. sweep/corners는 기술 통계이며 확률분포나 최악값
보장이 아닙니다.

`samples()`는 명시한 순서의 독립 변수, `sample_parameters()`는 전체 기하
인자만 반환합니다. `sample_material_evaluations()`는 실제 행별 재료 입력의
독립 복사본을 반환하며 잘못된 정규 표본도 보존합니다. 버전 4 결과의 각 행은
실패하더라도 실제 `material_evaluation_json`을 보존합니다. 단면 문서만으로는
재료 오버라이드를 재생할 수 없습니다. 전체 study 입력을 저장하고 개별 행 재생에는
해당 재료 입력도 사용해야 합니다. 공통 실행 어댑터는 버전 4를 읽고 행별
`material_evaluation`을 내보내며 이전 결과 형식은 유지합니다.

목표량은 `Re(C)`와 진공 외부 `L`에서 구한 실수 준정적 임피던스입니다.
손실 변동은 복소 필드 분포를 통해 이 값에 영향을 줄 수 있지만 감쇠·복소 특성
임피던스·수율·대역 목표가 아닙니다. 재료 fitting, 유효 주파수 확대, 행별 자동
메시 수렴은 제공하지 않습니다. 이미 빌드한 workbench의 엔진 pin은 별개로
유지되므로 이번 엔진 계약 추가가 기존 EXE나 웹 자산을 갱신하지 않습니다.

검증은 균일 재료의 `Z*sqrt(eps_real)` 불변식 상대 1e−10, 독립 Debye 식,
scikit-fem 12.0.2 복소 P1 계산과 임피던스 차이 1e−10, 엄격한 경로 검사,
동시 샘플링·실패 보존·저장 실행을 포함합니다. 기존 필드 기준과 세분화 검사도
유지합니다. 메시·필드 해법은 바꾸지 않았으며 실측 재료 정확도를 보장하지 않습니다.

```sh
python -m pytest -q tests/sipi/test_material_variables.py tests/sipi/test_material_impedance.py tests/sipi/test_study.py tests/sipi/test_stripline_studies.py tests/sipi/test_execution.py tests/sipi/test_sipi_references.py
```

[단일 재료 파라미터 역산(design v3)](material_goals.md)은 선택 모델과 세분 메시 수락을 보존합니다.
