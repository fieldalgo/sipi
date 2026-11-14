# 동일 기하의 유한 금속·유전체 선로 모델

[English](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/volume_line.md) | **한국어**

[도체 내부 확산](https://github.com/fieldalgo/sipi/blob/main/docs/locales/ko/pages/packages/sipi/conductor_diffusion.md) · [유전체 재료](https://github.com/fieldalgo/sipi/blob/main/docs/locales/ko/pages/packages/sipi/dielectrics.md) ·
[균일 선로 네트워크](https://github.com/fieldalgo/sipi/blob/main/docs/locales/ko/pages/packages/sipi/network.md)

`sipi.volume_line`은 유한 도체 내부의 DC·AC R과 전체 L, **같은 금속 표면**
주변 유전체의 C/G를 추출합니다. 엄격한 `sipi.volume-line/1`(공통 전도도) 또는
`/2`(이름별 금속) JSON 문서에
기하·재료 모델·전도도·부피 메시·주파수·길이·기준 임피던스를 저장합니다.
진공 안의 유한 유전체 상자와 유한 귀환 판을 정의하며 기존 상자 접지 기반
유전체 추출을 대신 끼워 넣지 않습니다.

```python
from sipi import CrossSectionDocument, microstrip
from sipi.volume_line import VolumeLineDocument

section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4, tan_delta=.02, air_height=.5e-3, box_width=2e-3)
doc = VolumeLineDocument(CrossSectionDocument(section), [0, 1e3, 1e5],
    materials={}, conductivity=58e6, relative_permeability=1, length=.1, z_ref=50,
    mesh=dict(ground_thickness=.1e-3, padding=2e-3, metal_size=12.5e-6,
              far_size=.125e-3, grade=.05, min_angle=28))
result = VolumeLineDocument.loads(doc.dumps()).analyze()
print(result.R, result.L, result.G, result.C)  # per-metre SI, (F,N,N)
print(result.network.s)                     # (F,2N,2N)
```

실행 [예제](https://github.com/fieldalgo/sipi/blob/main/examples/sipi/volume_line.py)는 입력 저장·복원을
거쳐 값을 출력합니다. 해상도·재료 한계가 있는 quasi-TEM/MQS 근사이며 전파장
해석이나 광대역 정확도 인증이 아닙니다. 금속·외부 메시와 상자 크기를 각각 검증해야 합니다.

## 공유하는 물리 기하

`mesh_conductor_section(..., dielectric_interfaces=True)`는 금속 다각형을
보존하면서 층 높이와 유전체 상자의 두 수직 벽에 정합하는 메시를 만듭니다.
층은 `[-width/2,width/2] × [0,height]`에서 금속을 뺀 영역에만 존재하며
나머지 비전도 부피는 진공입니다. 접지 두께와 자기 padding은
[도체 부피 계약](https://github.com/fieldalgo/sipi/blob/main/docs/locales/ko/pages/packages/sipi/conductor_diffusion.md)을 따릅니다. 독립 자기 메시 API에서는
이 옵션이 기본 False로 기존 메시 동작을 보존하고, 선로 문서에서는 항상 True입니다.

`dielectric_view(volume)`는 금속 삼각형을 제거하고 남은 노드를 재번호화하며
각 전극의 **동일 좌표**를 신호·귀환 전위 집합으로 매핑합니다. 반환값은
`(mesh, signals, ground, original_nonmetal_triangle_ids)`입니다. 보간이나
두 번째 기하 메싱은 없으며 자기 풀이에는 금속 내부가 모두 남습니다.

전기 외곽은 법선 D=0, 자기 외곽은 Az=0입니다. 서로 다른 장 방정식의 명시적
유한 영역 근사입니다. 모든 접지 판과 ground trace는 하나의 귀환입니다.
유전체 인터페이스는 전도도를 바꾸지 않습니다. 금속 밖은 0이며 저장 v1 입력은
금속 안에서 공통 양의 전도도를 씁니다. 직접 API는 전체 부피 메시의 요소별
양의 금속 전도도장도 받습니다([전도도 계약](conductor_diffusion.md)).
상대 투자율은 자기 영역 전체에 균일하며 메시·경계 수렴은 별도입니다.

`volume_line(volume, frequency, materials=..., conductivity=..., length=...,
z_ref=50, relative_permeability=1, keep_fields=False)`는 직접 메시 API입니다.
`MeshedConductors.layer_triangles`는 각 재료의 서로 겹치지 않는 비금속 삼각형을
지정해야 하며, 목록에 없는 비금속 삼각형은 진공입니다. `materials`에는 매핑된
모든 층을 정확히 한 번씩 지정하고 지원 [유전체 모델](https://github.com/fieldalgo/sipi/blob/main/docs/locales/ko/pages/packages/sipi/dielectrics.md)을 사용합니다.
직접 메시 호출자는 재료 분류를 책임지며 이 경로에서는 좌표로 재료를 추정하지 않습니다.
분수·boolean 영역 인덱스는 정수로 조용히 잘라 저장하지 않고 복사 전에 거부합니다.

각 주파수에서 C*는 유전체 submesh의 복소 정전용량입니다. exp(+jωt)에서
C=Re C*, G=−ω Im C*입니다. 네트워크에는 부피 전류의 R과 **전체 L을 한 번만**
사용하며 µεC0⁻¹을 다시 더하지 않습니다. 도체 표피 깊이·좋은 전도체 조건·전류·
에너지·상호성 검사는 유지됩니다. DC에서도 유한 직렬 저항을 보존하며 암묵적
무손실 통과, 표면/부피 자동 전환, 거칠기 외삽은 없습니다.

## 버전 문서와 출력

키를 정확히 검사하며 누락·추가 필드, 중복 JSON 키, 비유한 수, 수 대신 boolean,
알 수 없는 schema 버전을 거부합니다.

| 최상위 키 | 계약 |
|---|---|
| `schema` | 공통 스칼라 전도도는 `sipi.volume-line/1`, 이름별 금속 전도도는 `/2` |
| `cross_section` | 기존 `sipi.cross-section/1` 또는 `/2`, m 단위. 직사각 v2도 원 버전을 보존합니다. 유전체 전용 메시 옵션은 적용되지 않으므로 `mesh`가 비어 있어야 합니다. 모든 trace 두께는 양수입니다. |
| `mesh` | `ground_thickness`, `padding`, `metal_size`, `far_size`, `grade`, `min_angle` 여섯 키 모두 필수. 유한 양의 길이·각도, grade>=0, far_size>=metal_size, angle<34. |
| `materials` | 층 이름→버전 유전체 모델. 생략한 층은 단면의 상수 eps_r/tan_delta로 확정하여 명시적으로 저장합니다. 없는 층과 표 외삽/DC 오류는 메싱 전에 거부합니다. |
| `conductor` | `conductivity`(S/m), 양의 `relative_permeability`(전 영역 균일) 두 키만. v1 전도도는 양의 스칼라, v2는 아래 이름별 객체. 거칠기 필드 없음. |
| `frequency_hz` | 비어 있지 않은 음이 아닌 엄격히 증가하는 Hz 배열 |
| `length_m`, `reference_ohms` | 음이 아닌 길이, 양의 실수 스칼라 기준 임피던스 |

`dumps()`는 입력 JSON만 반환하며 `loads()`·`from_dict()`는 같은 검증을 사용합니다.
파일·네트워크 I/O는 없습니다. 호출자가 딕셔너리나 반환된 단면을 바꿔도 저장 문서는
바뀌지 않습니다. `analyze(keep_fields=True)`는 도체 결과에 Az/J를 보존하며 기본은
큰 장 배열을 저장하지 않습니다. 메싱 전 입력이 유효해도 실제 금속 변/표피 깊이
조건에서 실패할 수 있으며 이를 성공으로 반환하지 않습니다.

`VolumeLineResult`에는 `conductor`, 복소 (F,N,N) `C_complex`, `network`가 있습니다.
`frequency`, `names`, `R`, `L`, `G`, `C` 속성은 같은 신호 순서를 사용합니다.
`input_json`은 `VolumeLineDocument`로 풀면 확정 입력이고 직접 API에서는 None입니다.
C*는 복사 후 읽기 전용이며 도체 결과도 자체 불변 스냅샷·잔차를 보존합니다.
결과 객체 직접 생성은 검증 인증이 아닙니다. 포트 순서와 Touchstone 내보내기는
[네트워크 계약](https://github.com/fieldalgo/sipi/blob/main/docs/locales/ko/pages/packages/sipi/network.md)을 따릅니다.

## 검증과 제한

시험은 `tests/sipi/test_volume_line.py`와 기존 도체 부피·메시 시험입니다.
Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1, 시험 전용 scikit-fem 12.0.2를
사용했으며 새 런타임 의존성은 없습니다.

| 검사 | 기준과 측정 |
|---|---|
| 유한 동축 a=.5/b=1.5/c=2 mm | C*=2πε*/ln(b/a). 반경 8/16/32, 각도 256에서 오차 감소 및 최종 <.1%. 균일 Debye의 C*=ε*(f)C0는 1e-10 이내. |
| 동일 동축 메시의 복소 전기 풀이 | 독립 scikit-fem 복소 P1 조립·Dirichlet 풀이와 C* 상대 차이 4.00e-15, 기준 1e-9. 같은 메시 일치만으로 메시 정확도를 증명하지 않음. |
| 동일 직렬 모델 | 별도 부피 임피던스와 R/L 1e-12 이내 일치, 전체 L 중복 가산 없음. |
| 사다리꼴 내부를 지나는 층 경계 | 유전체 다각형 면적 1e-10 이내, 금속 제거 후 전극 좌표 집합 정확히 보존. |
| 유한 상자 microstrip, 금속 50→25→12.5 µm, 외부 .5→.25→.125 mm, grade .2→.1→.05 | C 변화 1.3478%→.53066%, G 1.7727%→.75816%. 최종은 원래 1% 기준 충족, 앞의 거친 두 메시 조합은 미달. |
| 최종 microstrip, padding 2→4 mm | C .24126%, G .04903% 변화로 각각 <2%. 유한 경계 오차는 별도. |
| 닫힌 접지 상자·Debye 유전체 | 다른 세분 메시의 기존 유전체 솔버와 C* 1% 이내. 닫힌 기하에만 해당하며 개방 무한 접지를 뜻하지 않음. |
| JSON·네트워크 | R/L/G/C 왕복 1e-12, S 1e-10 이내. 해석당 기하 메시 1회. 직사각 v1/v2·사다리꼴 v2 보존. 비대칭 두 신호 포트 순서·상호성/수동성 1e-10. |

초기 동축 메시(반경8·각도128)는 .22878%로 .1% 기준 미달이었고 허용값 변경 없이
세분했습니다. 유한 유전체 상자·전기 외곽은 기존 개방 상자 추출과 다르므로 값을
조용히 섞으면 안 됩니다. 이 문서는 표면 모델 입력 계약과 별개입니다.
비균일 투자율, 자동 거칠기, 방사, 임의 마스크 윤곽, 3D 전이는
미구현입니다. 재료 fit도 별도의 실측 검증이 필요합니다.

[주축 방향별 분산 재료](principal_dielectrics.md)는 저장 선로의 재료 매핑을 재사용합니다.

[전체 전방파 행렬 진단](characteristic.md)은 기존 스칼라 모드 계약을 유지하며 비대칭 상호 RLGC를 지원합니다.


## 이름별 금속 입력 (v2)

`VolumeLineDocument`에 `conductivity={'signals': {name: sigma, ...}, 'ground': sigma}`를
전달하면 `sipi.volume-line/2`를 선택합니다. 두 키 모두 필수이며 `signals`는
접지하지 않은 모든 trace 이름을 정확히 포함해야 합니다. 전도도는 S/m 단위의
유한한 양의 실수 스칼라이며 boolean은 허용하지 않습니다. 접지 trace 이름은
별도 신호 재료가 아닙니다. 모든 귀환 판·trace는 하나의 `ground` 값과 기존의
공통 종방향 전기장을 공유합니다. 중첩 매핑이므로 이름이 `ground`인 신호와도
충돌하지 않습니다.

```python
from sipi import CrossSectionDocument, coupled_microstrip
from sipi.volume_line import VolumeLineDocument
from sipi.execution import normalize_saved

section = coupled_microstrip(
    width=.4e-3, gap=.3e-3, substrate_height=.5e-3, thickness=.1e-3,
    eps_r=4., tan_delta=.02, box_width=.003, air_height=.001,
)
doc = VolumeLineDocument(
    CrossSectionDocument(section), [0, 1e3, 1e4], materials={}, length=.1,
    conductivity=dict(signals={'positive': 58e6, 'negative': 20e6}, ground=10e6),
    mesh=dict(ground_thickness=.1e-3, padding=.002, metal_size=50e-6,
              far_size=.5e-3, grade=.2, min_angle=28.),
)
assert doc.to_dict()['schema'] == 'sipi.volume-line/2'
assert normalize_saved(doc.dumps()) == doc.dumps()
result = VolumeLineDocument.loads(doc.dumps()).analyze()
assert result.names == ('positive', 'negative')
```

메시 생성 전에 이름과 값을 검증하고, 새 부피 메시마다 그 이름으로 전도도장을
다시 배정합니다. 저장 입력에는 삼각형 인덱스가 없습니다. 누락·외부 이름,
숫자 배열, 잘못된 값, 추가 키를 거부합니다. v1은 이름별 매핑을 받지 않고,
v2는 스칼라를 조용히 변환하지 않습니다. 기존 v1 JSON은 바이트 단위로
보존합니다. 균일 재료의 v2는 조각별 풀이를 쓰며 v1과 정규화 1e-12 이내로
일치하는지 검사합니다.

공통 저장 실행기와 회로의 `kind='volume-line'` 입력도 같은 엔진으로 v2를
재생합니다. 명시적 메시 전도도장과 R/L/C/G·네트워크 값을 비교하고, 두 신호의
DC 면적 저항 해석해를 1e-10으로 검사하며, 재메시 후 재료 배정을 확인합니다.
기존 혼합 금속 Bessel·독립 조립 및 부피 메시·외곽 기준은 별도로 유지합니다.
이 형식은 도체 이름마다 하나의 재료를 지정합니다. 한 도체 안의 도금 계면,
임의 공간장, 온도 법칙이나 보정된 거칠기를 생성·저장하는 형식은 아닙니다.

명시적 코어·도금 계면 저장은 [volume-line v3](metal_cores.md#계면과-재료-저장)를 사용합니다.

[Volume-line v4](spatial_permeability.md#volume-line-v4의-이름별-자기-재료-저장)는 이름별 선형 자기 재료를 저장합니다.
