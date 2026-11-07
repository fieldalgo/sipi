# 지정 주파수 재료를 사용하는 임피던스 공차·역산

공차 study와 구간 역산에 `frequency`(Hz)와 `materials` 매핑을 함께 전달할 수 있습니다.
[주파수 선로 해석](principal_dielectrics.md)과 같은 스칼라·주축 모델을 사용하며,
기하 샘플마다 새 메시를 만들고 저장된 주파수에서 고정 재료 모델을 평가합니다.
두 인자를 모두 생략하면 기존 상수 단면 동작과 JSON을 그대로 유지합니다.
빈 매핑을 명시하면 단면의 원래 스칼라 기본값을 사용합니다.

결과는 기존의 **실수 준정적 임피던스**입니다. 단일 선로는
`z0=sqrt(L_external/Re(C_complex))`, 대칭 쌍은 `z_diff=2*z_odd`입니다.
명시적 [`z_diff_forward`](asymmetric_pair.md)는 전체 실수 전방 전류 행렬을 사용하며
기울어진 텐서를 포함한 비대칭 쌍을 허용합니다.
외부 L은 진공 C0에서 구합니다. 복소 유전체 손실은 정전계와 C에 영향을 주지만,
이 값은 `sqrt((R+jωL)/(G+jωC))`라는 복소 손실 특성 임피던스나 감쇠 목표·대역
최적화가 아닙니다. 도체 손실 근사를 묵시적으로 선택하지 않습니다.

## 기하 공차 study

```python
from sipi.dielectric import PrincipalAxisDielectric, DebyeDielectric, ConstantDielectric
from sipi.study import ImpedanceStudyDocument

material = PrincipalAxisDielectric(
    DebyeDielectric(2, [2], [1e8]), ConstantDielectric(5, .02), angle_rad=0,
)
parameters = dict(width=.5e-3, substrate_height=.5e-3, eps_r=4,
                  thickness=35e-6, air_height=4e-3, box_width=8e-3)
mesh = dict(edge_size=4e-6, far_size=.25e-3, grade=.2)
study = ImpedanceStudyDocument(
    'microstrip', parameters, quantity='z0', mesh=mesh,
    frequency=1e8, materials={'substrate': material},
    sampling=dict(kind='sweep', count=2,
                  variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]),
)
saved = study.dumps()
result = ImpedanceStudyDocument.loads(saved).analyze()
assert result.failed == 0
result.summary, [row.impedance for row in result.rows]
```

이 모드는 **기하 변수만** 샘플링합니다. `eps_r`나 `tan_delta`가 이름에 들어가는
템플릿 변수는 일부 영역에만 재료를 지정했어도 거부합니다. 재료 변동을 지정해 놓고
override에 의해 실제로 무시하는 일을 막기 위한 규칙입니다. 모델 파라미터·축 각도
공차는 미지원입니다. sweep·corners·uniform·상관 normal의 순서·seed·경계·실패 처리는
유지합니다. 유효하지 않은 normal 행은 재추출 없이 실패로 남기고, 하나라도 실패하면
전체 요약 통계를 만들지 않습니다. 고정 수평 pitch·전체 평면 간격도 기존 템플릿 제한을 따릅니다.

`z_diff`에서는 평가한 텐서가 메시 x/y에서 상대 `1e-12` 이내 대각행렬이어야 합니다.
기울어진 비등방 재료는 교환 대칭을 가정하지 않고 **메시 전에 거부**합니다.
같은 두 축은 회전 각도와 무관하게 등방성입니다. 계산한 쌍에는 기존의 자기 정전용량
1% 대칭 관문도 적용하고, 통과한 뒤 자기항 평균을 사용합니다. 일반 비대칭 모드 해석기나
임의 기하의 대칭성 증명을 제공하는 것은 아닙니다.

## 별도 세분화 확인이 있는 구간 역산

```python
from sipi import ImpedanceDesignDocument

goal = ImpedanceDesignDocument(
    'microstrip', parameters, variable='width', bounds=[.3e-3, .9e-3],
    target=60, quantity='z0', tolerance=1, max_evaluations=24, mesh=mesh,
    frequency=1e8, materials={'substrate': material},
)
solution = ImpedanceDesignDocument.loads(goal.dumps()).solve()
assert abs(solution.residual) <= 1
assert abs(solution.refined_residual) <= 1
solution.parameter, solution.material_evaluation_json
```

요청 메시와 세분 메시 모두 같은 주파수·재료를 사용합니다. 이분법·목표 구간 검사·
평가 예산·완료된 실패 이력·필수 최종 세분화는 그대로입니다. 구간이 목표를 감싸지
않거나 세분 메시가 목표를 벗어나면 여전히 `GoalSeekError`입니다. 성공은 제조 공차
인증이나 외곽 수렴 증거가 아니므로 박스 크기는 별도로 검사해야 합니다.

직접 API `seek_impedance(factory, bounds, target, ..., frequency=..., materials=...)`도
같은 고정 재료 지정을 받습니다. 일반 factory가 어떤 변수를 뜻하는지는 호출자가
정하며 엔진이 추정하지 않습니다. 저장 역산 문서의 이름 있는 변수는 기하로 제한합니다.

## 정확한 저장 계약과 재실행

기존 `sipi.impedance-study/1`, `/2`, `sipi.impedance-design/1`은 불변입니다.
재료 study는 `/3`이며 `material_evaluation`을 추가하고 `fixed_plane_spacing_m`을
null이어도 포함합니다. 재료 역산은 `/2`이며 기존 필드에 `material_evaluation`을
추가합니다. 이 객체에는 `frequency_hz`와 `materials`만 있으며, 각 재료는 완전한
`sipi.dielectric/1` 또는 `/2` 기록입니다. 주파수는 유한 비음수 실수 스칼라입니다.
알 수 없는/누락 필드·잘못된 모델·미등록 영역·표 범위 오류는 메시 전에 거부합니다.
공개 인자 두 개도 반드시 함께 지정해야 합니다.

study의 `input_json`에는 전체 조건이 들어갑니다. 각 `StudyRow.document`는 여전히
**기하**만 저장하므로 행을 재현하려면 전체 study JSON을 보존해야 합니다.
역산 결과도 `document`는 기하이며, 추가 조건은 불변 문자열
`material_evaluation_json`에 보존합니다(기존 결과는 None). 둘 다 저장하거나 역산
입력 문서를 저장하세요. `document.analyze()`만 실행하면 원래 스칼라 기본값을 사용합니다.

단일 선로 study 행을 재료 조건까지 포함해 다시 계산하는 예입니다.

```python
import json
import numpy as np
from sipi.dielectric import dielectric_from_dict, dispersive_line

evaluation = json.loads(result.input_json)['material_evaluation']
models = {name: dielectric_from_dict(record)
          for name, record in evaluation['materials'].items()}
row = result.rows[0]
sweep = dispersive_line(row.document.section, [evaluation['frequency_hz']],
                        materials=models, **row.document.mesh_options)
replayed_z0 = np.sqrt(sweep.L[0, 0] / sweep.C[0, 0, 0])
assert np.isclose(replayed_z0, row.impedance, rtol=1e-10, atol=0)
```

## 검증

`python -m pytest -q -s tests/sipi/test_material_impedance.py`와 기존 study·제약·
역산·재료 시험을 실행합니다. 독립 scikit-fem 12.0.2의 복소/진공 해석으로 단일·쌍
샘플 임피던스를 상대 `1e-9`로 비교합니다. 균일 재료는
`Z=Z_vac/sqrt(Re eps)`를 상대 `1e-10`으로 만족해야 합니다. 독립 Cohn 스트립라인
식과 분산 재료 폭 역산의 차이는 1% 이내, 양쪽 메시 잔차는 0.25Ω 이내여야 합니다.
텐서 폭 목표는 양쪽 잔차 1Ω 이내를 요구합니다. 기존 텐서 메시·외곽 수렴 시험도
유지합니다. JSON 호환성·샘플 재현·제약 결합·복사·입력 사전 거부·normal 실패 행·
해석 예산은 별도로 검사합니다.

이 작업이 실측 적층재·통계적 수율·재료 피팅·일반 비대칭 전파·새 운영체제·
브라우저·무설치 입력 화면을 검증했다는 뜻은 아닙니다.

[Study](study.md) · [역산](design.md) · [재료](principal_dielectrics.md) ·
[English](../../../../../packages/sipi/material_impedance.md)

[재료 파라미터 공차 분석(v4)](material_variables.md)은 명시한 재료 모델 항목의 변동을 지원합니다.
