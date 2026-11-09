# 항마다 독립 방향을 갖는 Debye 텐서

[English](../../../../../packages/sipi/tensor_debye.md) · [고정 주축](principal_dielectrics.md) · [재료 공차](material_variables.md) · [재료 역산](material_goals.md)

`TensorDebyeDielectric`는 고주파 텐서와 각 양의 준정부호 Debye 잔차가 서로
다른 실수 회전 방향을 갖는 상반 횡방향 상대 유전율입니다. 주파수 단위는 Hz,
각도는 전역 횡방향 x축에서 반시계 방향 라디안입니다. 시간 규약은
`exp(+j omega t)`이며 다음 유한 합을 계산합니다.

`eps(f) = R(theta_inf) diag(eps_inf) R(theta_inf)^T
        + sum_k R(theta_k) diag(strengths_k) R(theta_k)^T / (1 + j*f/pole_k)`.

`eps_inf`는 각각 1 이상인 유한 실수 두 개입니다. `strengths`는 음수가 아닌
유한 실수 쌍 1–64개, `relaxation_hz`는 항마다 양의 유한 극점 주파수 하나,
`angles_rad`는 같은 길이의 유한 실수 각도 배열입니다. `eps_inf_angle_rad`는
기본값 0인 유한 실수 스칼라입니다. 불리언·복소수 입력은 거부합니다.
보수적 정적 상한 `max(eps_inf) + sum(max(strengths_k))`도 유한해야 합니다.
입력은 불변 튜플로 보관하며 반환 배열과 문서는 내부 상태와 분리됩니다.
스칼라 주파수는 `(2,2)`, 비어 있지 않은 주파수 벡터는 `(F,2,2)`를 반환합니다.
재료 자체 평가는 0 Hz를 허용하고 선로 분석은 기존 양의 주파수 조건을 유지합니다.

잔차 방향이 다르면 실수부와 손실부의 주축이 주파수에 따라 변하고 서로 일치하지
않을 수 있습니다. 공통 회전 좌표계나 고유벡터 추적을 가정하지 않습니다.
`Re(eps)`는 양의 정부호, `-Im(eps)`는 양의 준정부호입니다. 비대각 성분 하나의
부호만으로 수동성을 판단할 수 없습니다. 각 인과적 완화항의 임펄스 응답은
`2*pi*pole_k*A_k*exp(-2*pi*pole_k*t)*H(t)`이고 Laplace 극점은 음의 실수입니다.
이는 유한 모델족의 성질이며 실제 적층재나 임의 인과적 이방성 스펙트럼의 검증이
아닙니다. 종방향·자기 응답, 전파 전체 해석, 텐서 재료 피팅은 범위 밖입니다.

## 재료 입력과 저장 선로

```python
import json
import numpy as np
from sipi import CrossSectionDocument, coupled_microstrip
from sipi.dielectric import TensorDebyeDielectric, dielectric_to_dict, dielectric_from_dict
from sipi.line_model import TransmissionLineDocument
from sipi.execution_request import SavedExecutionRequest

material = TensorDebyeDielectric(
    eps_inf=[2, 3], strengths=[[4, .5], [.25, 3]],
    relaxation_hz=[1e8, 1e10], angles_rad=[0, np.pi/4],
)
record = dielectric_to_dict(material)
assert record['schema'] == 'sipi.dielectric/3'
assert dielectric_from_dict(json.loads(json.dumps(record))) == material
section = coupled_microstrip(width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, thickness=35e-6, eps_r=4,
    box_width=8e-3, air_height=4e-3)
document = TransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=10e-6, far_size=.25e-3, grade=.2)),
    [1e6, 1e8, 1e10], materials={'substrate': material},
    conductor={'kind': 'perfect'}, length=.01,
)
request = SavedExecutionRequest(document.dumps(), max_evaluations=3)
receipt = request.run()
assert receipt['execution']['status'] == 'complete'
assert receipt['execution']['input'] == document.to_dict()
```

중첩 재료 형식은 정확히 `sipi.dielectric/3`, 종류는 `tensor-debye`입니다.
`parameters`에는 기본 각도까지 포함한 다섯 생성자 필드가 모두 있어야 합니다.
추가·누락 키와 잘못된 필드는 거부합니다. 스칼라 `/1`과 고정 주축 `/2`의 의미는
유지하며 `PrincipalAxisDielectric`의 자식으로 텐서를 넣을 수 없습니다.
기존 선로·공차·역산 입력 안에 새 재료 버전을 넣으므로 최상위 저장 스키마는
늘어나지 않습니다. 구버전 판독기는 이를 거부합니다.
기하의 `eps_r`는 여전히 스칼라입니다. `section.analyze()`만 호출하면 기하에
저장한 기본 재료를 사용하므로 주파수별 재료 매핑으로 이 모델을 적용해야 합니다.
예제 메시와 요청 식별자는 임의 설계의 정확도·호스트 취소·플랫폼 지원을 보증하지
않습니다.

## 재료 변화

기존 재료 변수 바인딩으로 `['strengths', 0, 0]`, `['relaxation_hz', 0]`,
`['angles_rad', 1]` 같은 숫자 필드를 선택합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

study = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
         substrate_height=.5e-3, eps_r=4, left_thickness=35e-6,
         right_thickness=50e-6, box_width=12e-3, air_height=6e-3),
    quantity='z_diff_forward', frequency=1e8,
    materials={'substrate': material},
    material_variables={'d': dict(region='substrate', path=['strengths', 0, 0])},
    sampling=dict(kind='uniform', count=2, seed=71,
                  variables=[dict(name='d', lower=2, upper=4)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze()
assert result.failed == 0
for row, sample in zip(result.rows, study.samples()):
    actual = json.loads(row.material_evaluation_json)
    assert actual['materials']['substrate']['parameters']['strengths'][0][0] == sample[0]
```

저장 공차 `/4`는 잘못된 정규분포 표본도 원래 재료 스냅샷과 분모를 유지한 실패로
남기며 다시 추출하지 않습니다. 저장 역산 `/3`은 기하와 관측 주파수를 고정하고
양의 숫자 필드 하나를 탐색합니다. 선택된 재료 스냅샷을 세분 메시에도 재사용합니다.
목표는 `Re(C)`와 진공 외부 인덕턴스에서 구한 실수 준정적 임피던스입니다.
복소 임피던스·감쇠 최적화로 바뀌지 않으며 해의 유일성, 실제 재료 조달 가능성,
실측 유효성을 보장하지 않습니다. 기존 예산·목표 구간·원/세분 잔차 조건을 유지합니다.

## 검증 범위

```sh
python -m pytest -q -s tests/sipi/test_tensor_debye.py tests/sipi/test_tensor_debye_fields.py
```

독립적으로 저장한 유리식·회전 기준, 고정축·등방성 축소, 수동성, 회전 공변성,
불변/엄격 입력, 극단적인 유한 주파수를 검사합니다. 독립 기준 계약과 생성기는
`tests/sipi/reference_data/tensor_debye`에 보관합니다. 기준값을 다시 만드는 것으로
커밋된 기준과의 비교를 대체할 수 없습니다.

복소 다층 축전기는 상대오차 `1e-9` 미만을 요구합니다. 변환 타원 동축은 세 단계
반경/각도 세분화에서 오차 감소, 최종 오차 0.1% 미만, 마지막 관측 수렴차수 1.5
이상을 요구합니다. 서로 다른 방향을 가진 결합 선로는 1 MHz·100 MHz·10 GHz에서
scikit-fem 12.0.2 독립 텐서 조립과의 정규화 복소 C 오차 `1e-9` 미만, 메시·상자
폭·공기 높이의 각각 독립 변화 1% 미만을 요구합니다. 네트워크 상반성·수동성
허용치는 `1e-10`입니다. 지정한 사례의 수치 검증이며 임의 기하 인증이 아닙니다.

재료 공차 두 표본은 선택된 스냅샷으로 직접 재계산하여 상대 `1e-10` 이내를
요구합니다. 등방성 극점 역산은 유효 유전율 3.5의 독립 Cohn stripline 식을 목표로
쓰며 극점이 100 MHz에서 1.5% 이내, 원/세분 메시 잔차 모두 0.1 ohm 이내여야 합니다.
이는 독립 해석적 목표로 재료 역산 연결을 검사하며 일반 이방성 임피던스 공식은
아닙니다. 실측 데이터·새 플랫폼·브라우저·무설치 실행 파일 검증을 뜻하지 않습니다.
