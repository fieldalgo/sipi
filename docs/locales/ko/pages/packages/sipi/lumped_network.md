# 수동 집중정수 RLC 네트워크

`lumped_network`는 **직렬 R-L-C 가지 하나**로 2포트 네트워크를 만듭니다.
이를 선로 사이에 직렬로 넣거나(`series`), 이상적인 통과 노드와 공통 접지
사이에 연결합니다(`shunt`). 시간 규약은 `exp(+j omega t)`, 단위는 SI,
파동은 전력 정규화입니다. 기하에서 부품값이나 기생 성분을 추정하지 않습니다.

```python
from sipi import LumpedNetworkDocument, NetworkTransformDocument
from sipi.circuit_document import CircuitDocument

branch = LumpedNetworkDocument(
    [0, 1e6, 1e9, 10e9], resistance=.23, inductance=1.2e-9,
    capacitance=2.2e-12, placement='series', z_ref=[25, 85],
    port_names=('input', 'output'),
)
restored = LumpedNetworkDocument.loads(branch.dumps())
network = restored.analyze()
circuit = CircuitDocument(
    dict(kind='lumped-network', document=restored.to_dict()),
    excitation=dict(kind='sources', voltages={'input': 1}),
    terminations={'input': 37, 'output': 83},
)
response = circuit.analyze().response
assert abs(response.voltage[0, 1]) < 1e-12
reduced = NetworkTransformDocument(
    dict(kind='lumped-network', document=restored.to_dict()),
    operations=[dict(kind='terminate-ports', loads={'output': 83})],
).analyze().network
```

## 계약과 저장 입력

양의 주파수에서 `Z = R + j 2 pi f L + 1/(j 2 pi f C)`입니다.
`resistance`(Ω)와 `inductance`(H)는 유한한 비음수 상수이며 기본값은 0입니다.
`capacitance`(F)는 유한한 양수 또는 `None`입니다. `None`은 커패시터의
**생략**이지 0 F나 개방 가지가 아닙니다. 병렬 RLC 조합을 자동으로 만들지 않습니다.

`frequency`는 유한한 Hz >= 0의 비어 있지 않은 엄격 증가 1차원 배열입니다.
`z_ref`는 양의 실수 상수 하나 또는 포트별 두 상수입니다. 복소수·주파수별
기준은 받지 않습니다. `port_names`는 비어 있지 않은 고유한 한 줄 이름 두 개로,
near 다음 far 순서입니다. 기본값은 near·far이며 양쪽 전류는 네트워크 안으로
향합니다. 반환하는 single-ended `LineNetwork`는 읽기 전용 배열 사본을 가집니다.

DC에서 커패시터가 있으면 가지는 정확히 개방입니다. series는 서로 분리된
개방 포트, shunt는 통과 연결입니다. 커패시터가 없으면 Z=R이며, R=0이면
series는 통과, shunt는 접지 단락입니다. 무한대를 큰 유한값으로 대체하지 않습니다.

엄격한 `sipi.lumped-network/1` 객체의 필드는 다음뿐입니다.

| 필드 | 값 |
|---|---|
| `schema` | `sipi.lumped-network/1` |
| `frequency_hz` | 증가 주파수 배열 |
| `branch` | `resistance_ohms`·`inductance_h`·`capacitance_f`만 포함, C는 숫자 또는 null |
| `placement` | `series` 또는 `shunt` |
| `reference_ohms` | 양의 scalar 또는 길이 2 배열, 정규 출력은 전체 배열 |
| `port_names` | 명시 이름 두 개, 정규 출력은 배열 |

`from_dict`·`loads`·`to_dict`·`dumps`는 복사한 정규 입력을 보존합니다.
알 수 없는/누락 필드, 중복 JSON 키, 미지원 버전, 불리언 숫자와 비유한 값은
오류입니다. `analyze()`는 `LineNetwork`를 반환합니다. 입력 해석 시 수치 범위도
검사하지만 메시 생성이나 파일 I/O는 하지 않습니다.

`{"kind":"lumped-network", "document":branch.to_dict()}`를
[회로](circuit_document.md)·[조립](network_assembly.md)·[변환](network_document.md)
입력에 넣을 수 있습니다. 기존 필드 의미와 옛 정규 JSON은 유지하며 옛 reader는
새 kind를 거부합니다. 집중정수 구성 요소의 회로/조립 extraction은 `None`입니다.
기하 구성 요소는 기존 진단을 보존하고 분석마다 한 번씩 추출합니다.

## 수치 범위와 검증

정규화 산란 계수로 큰 기준 임피던스끼리의 곱과 절대 병렬 저항 나눗셈을
피합니다. 실수·허수 성분을 따로 나눠 pure-R에서는 subnormal 저항·기준도
지원합니다. 리액턴스 곱은 이진 지수를 분리합니다. 양의 주파수에서 각 비영
유도성/용량성 리액턴스는 **normal인 유한 binary64** 값이어야 합니다.
subnormal·underflow·overflow는 `ValueError`입니다. 유한 L/C의 정확한 상쇄는
허용하지만 공진 부근 상대 임피던스 정확도는 상쇄 조건에 좌우됩니다.
정규화 보정이나 수동성 복구는 하지 않습니다.

독립 scikit-rf 2.2.0(시험 전용, BSD-3-Clause)에서 실제의 서로 다른 포트 기준으로
ABCD를 직접 구성합니다. 최대 절대 S·KCL/KVL·스케일을 맞춘 옴 법칙·전력 잔차의
관문은 `1e-10`입니다. 시험한 >= 1 MHz에서는 원래 전압 법칙 잔차도 `1e-10 V`를
만족해야 하며, 높은 임피던스의 1 kHz는 스케일을 맞춘 법칙으로 검사합니다.
100자리 Decimal 독립식으로 최소 양의 float부터 `1e300`까지 pure-R 2,000조합을
검사합니다. 절대 S 오차와 subnormal을 넘는 전송값의 상대 오차는 각각 `1e-12`
이하입니다. 이는 2,000개의 별도 시험 함수가 아닌 매개변수 조합 수입니다.
DC 극한·LC 공진·수동성/유니터리성·상반성·기준/임피던스 스케일·해석적 Thevenin
V/I와 전력·JSON 재생·기하/회로 연결도 검사합니다.

기존 cascade·deembedding에도 연결됩니다. S가 특이해도 제거 가능한 fixture가
있습니다. 반면 DC 직렬 커패시터처럼 전송이 0인 fixture는 그 샘플에서 제거할 수
없어 기존 조건수 관문에서 거부하며 샘플을 조용히 버리지 않습니다. 대수적 가지에
FEM 수렴 시험은 적용되지 않고 기하 구성 요소에는 기존 수렴 조건이 유지됩니다.

다단자 상호 성분, 주파수 의존 부품 fitting, 비선형/온도 의존 소자, 분포형 AC
전원면, 물리적 비아·패드·안티패드 전이, 시간영역 솔버는 아닙니다. 실측 부품
정확도나 새 플랫폼 실행을 뜻하지 않습니다. 새 런타임 의존성을 추가하지 않습니다.

[English](../../../../../packages/sipi/lumped_network.md)
