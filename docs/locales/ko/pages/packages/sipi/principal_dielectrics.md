# 주축 방향별 분산 유전체

`sipi.dielectric.PrincipalAxisDielectric(axis1, axis2, angle_rad=0)`는 기존 스칼라
재료 모델 두 개를 고정된 직교 횡방향 축에 배치합니다.

`eps(f) = R(angle) diag(eps1(f), eps2(f)) R(angle)^T`.

축 1은 **메시의 전역 x축**에서 반시계 방향으로 `angle_rad`만큼 회전하며 축 2는
그에 수직입니다. 각도는 음수도 가능한 유한 실수 라디안입니다. 각 축에는
`ConstantDielectric`, `DebyeDielectric`, `WidebandDielectric`, `TabulatedDielectric`
중 하나를 지정합니다. 주축 모델의 중첩은 거부합니다. 회전은 실수이고 주파수에
따라 바뀌지 않습니다. 두 축의 분산과 손실은 달라도 되며, 각 구성 모델의 유효범위와
인과성 제한을 그대로 따릅니다.

스칼라 주파수의 결과는 `(2,2)`, 주파수 배열의 결과는 `(F,2,2)`입니다.
상대 유전율의 실수부는 양의 정부호이고 `exp(+jωt)`에서 손실 행렬 `−Im(eps)`는
양의 준정부호입니다. 비대각 허수부가 양수여도 수동 행렬일 수 있습니다.
계수는 무차원 횡방향 상대 유전율이며, 종방향 결합·자기 이방성·비상호성은 범위 밖입니다.

## 선로 입력 저장과 재실행

```python
from sipi import CrossSectionDocument, microstrip
from sipi.dielectric import PrincipalAxisDielectric, DebyeDielectric, WidebandDielectric
from sipi.line_model import TransmissionLineDocument

section = microstrip(width=.4e-3, substrate_height=.5e-3,
                     thickness=.1e-3, eps_r=4,
                     air_height=.5e-3, box_width=2e-3)
material = PrincipalAxisDielectric(
    DebyeDielectric(eps_inf=2, strengths=[3], relaxation_hz=[1e8]),
    WidebandDielectric(eps_ref=4, tan_delta_ref=.02, reference_hz=1e9),
    angle_rad=.4,
)
document = TransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=10e-6, far_size=.25e-3, grade=.2)),
    [1e6, 1e8, 1e10], materials={'substrate': material},
    conductor={'kind': 'perfect'}, length=.01,
)
saved = document.dumps()
result = TransmissionLineDocument.loads(saved).analyze()
result.C, result.G, result.L, result.network.s
result.dielectric.layer_permittivity['substrate']  # read-only (3,2,2)
```

완전도체 선택은 R=0을 명시합니다. 표면도체 및 유한 체적 선로도 같은 재료 기록을
받으며 기존 표피 깊이·메시·전류 보존 관문을 유지합니다. 도체의 R 및 인덕턴스 계산은
변하지 않습니다. 동일 기하 메시에서 주파수마다 텐서 유전율로 C/G를 계산합니다.
예제의 메시 설정은 입력 예시이며 임의 설계의 수렴을 보장하지 않습니다.

`dispersive_line`의 `materials`에도 주축 객체를 전달할 수 있습니다. 생략한 층은
원래 스칼라 기본값을 유지하며 스칼라·텐서 영역이 함께 있을 수 있습니다. 텐서 해석
내부에서만 스칼라 계수를 단위행렬 배수로 바꿉니다. `DielectricSweep.layer_permittivity`는
실제로 평가한 스칼라 `(F,)` 또는 텐서 `(F,2,2)` 형태를 복사해 읽기 전용으로 보존합니다.
진공 C0와 외부 준TEM 인덕턴스 관계는 유지됩니다. 기울어진 재료는 선로 쌍의 교환
대칭을 깨뜨릴 수 있으므로 짝/홀 모드 전파 지원을 자동으로 뜻하지 않습니다.

## 버전 있는 재료 계약

스칼라 `sipi.dielectric/1` 형식은 그대로입니다. 주축 기록은 `sipi.dielectric/2`,
`kind: "principal-axes"`이며 parameters에는 다음 세 필드만 들어갑니다.

```python
from sipi.dielectric import dielectric_to_dict, dielectric_from_dict

record = dielectric_to_dict(material)
assert record['schema'] == 'sipi.dielectric/2'
assert set(record['parameters']) == {'axis1', 'axis2', 'angle_rad'}
assert record['parameters']['axis1']['schema'] == 'sipi.dielectric/1'
restored = dielectric_from_dict(record)
```

두 축 값은 모든 생성자 필드를 포함하는 완전한 스칼라 `/1` 기록입니다. 알 수 없는
필드·누락·bool/비유한 각도·미지원 모델·중첩 모델을 거부합니다. 표 모델은 양의 주파수
범위를 유지하며 범위 밖 주파수는 메시 생성 전에 거부합니다. 기존 transmission-line과
volume-line 스키마 안에 새 **재료** 버전을 저장합니다. 조립·네트워크 변환·회로 문서도
그대로 보존하고 재실행합니다. 이전 판독기는 새 중첩 재료 스키마를 거부합니다.

`Layer`, 템플릿의 `eps_r`, 기하 JSON은 여전히 스칼라 재료를 사용합니다. 텐서는
주파수 선로 재료 매핑 또는 [지정 주파수 재료 study/역산 계약](material_impedance.md)으로 지정하며,
`section.analyze()`만 호출하면 원래 스칼라 기본값을 사용합니다. 이번 작업에서
브라우저·무설치 프로그램 입력 화면까지 연결한 것은 아닙니다.

## 검증

```sh
python -m pytest -q -s tests/sipi/test_principal_dielectric.py tests/sipi/test_tensor_electrostatics.py
```

- 회전/고유값 불변식, 축 교환과 π/2 회전, 등방성 환원, 엄격한 저장/복원과 메시 전
  거부를 검사합니다. 같은 두 축은 스칼라 C/G/L/R을 상대 `1e-12`, S를 절대 `1e-10`으로 재현합니다.
- 정렬된 층별 평행판에서 독립 복소 직렬식 `eps0 W / sum(h/eps_yy(f))`와 상대 `1e-9` 이내로 일치해야 합니다.
- 비례 Debye 축 `eps=A*k(f)`의 변환 타원 동축에서는
  `C=2*pi*eps0*sqrt(det A)*k(f)/ln(b/a)`를 사용합니다. 반경/각도 분할
  16/64 → 32/128 → 64/256에서 오차 감소·차수 ≥1.5·최종 0.1% 미만을 요구합니다.
  외곽 전극은 실제 경계입니다.
- 스칼라/텐서 혼합 결합 마이크로스트립의 1MHz/100MHz/10GHz 복소 C를 scikit-fem
  12.0.2의 독립 텐서 조립과 비교하며 최대 상대 차이 관문은 `1e-9`입니다. 별도로
  가장자리 4→1μm 세분화와 박스/공기 크기 두 배 확대의 복소 C 원소 최대 상대 변화가 각각 1% 미만이어야 합니다.
- 저장된 완전/표면도체 및 체적 선로, 조립, 기준 임피던스 변환, 구동 회로의 입력 보존과 기존 추출 계약을 확인합니다.

이는 명시한 수치 문제의 검증입니다. 실측 적층판, 주파수마다 바뀌는 일반 고유축,
3D 전이, 전파 전체장 또는 새 운영체제 검증을 뜻하지 않습니다. 구성 재료의 인과성만으로
주파수 샘플 네트워크의 시간영역 인과성이 인증되지는 않습니다.

[스칼라 재료](dielectrics.md) · [메시 텐서 API](tensor_electrostatics.md) ·
[저장 선로](line_model.md) · [체적 선로](volume_line.md) ·
[English](../../../../../packages/sipi/principal_dielectrics.md)
