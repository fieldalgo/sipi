# 주파수 표본별 네트워크 대역 제한

[English](../../../../../packages/sipi/band.md) · [저장 실행](execution.md)

`NetworkBandDocument`는 네트워크와 `abs(S[output_port, input_port])` 제한을
저장합니다. 해당 power-wave 기준의 삽입·반사·누화·모드 변환을 검사하며,
나머지 포트는 네트워크의 기준 임피던스로 종단됩니다. 실제 부하를 연결한
전압 누화 비율과는 구분합니다.

```python
from sipi.band import NetworkBandDocument, db_to_magnitude
from sipi.lumped import LumpedNetworkDocument

network = dict(kind='lumped-network',
    document=LumpedNetworkDocument([0, 1e8, 2e8], resistance=25).to_dict())
plan = NetworkBandDocument(network, limits=[dict(
    name='insertion', input_port='near', output_port='far',
    frequency_hz=[0, 2e8], minimum=db_to_magnitude(-3), maximum=None)])
result = NetworkBandDocument.loads(plan.dumps()).analyze()
assert result.passed
assert result.to_dict()['coverage'] == 'frequency-samples-only'
```

`sipi.network-band/1`의 정확한 필드는 `schema`, `network`, `basis`, `limits`입니다.
입력 종류는 기존 `rlgc`, `touchstone`, `lumped-network`, `transmission-line`,
`volume-line`, `network-assembly`, `network-transform`이며 원래 문서와 물리 검증을
그대로 사용합니다. 파싱 중 기하 필드를 계산하지 않습니다. RLGC·집중소자
검증기는 작은 네트워크 계산을 수행할 수 있습니다.

`basis`는 `single-ended` 또는 명시적인 `mixed-mode` 변환입니다. 후자는 같은
기준 임피던스의 네 포트가 near+/near-/far+/far- 순서여야 합니다. 출력은
 d_near,d_far,c_near,c_far 순서이고 차동 기준은 2Z, 공통 기준은 Z/2입니다.
포트 이름의 철자로 물리적 배치를 추론하지 않으며 사용자가 순서를 지정해야 합니다.

제한은 1–64개이며 각 객체는 다음 필드만 갖습니다.

| 필드 | 의미 |
|---|---|
| `name` | 중복 없는 비어 있지 않은 한 줄 이름 |
| `input_port`, `output_port` | 선택한 기준의 기존 포트 이름 |
| `frequency_hz` | 입력 주파수 배열에 정확히 존재하는 오름차순 양 끝점 |
| `minimum`, `maximum` | 유한한 0 이상 선형 크기 제한 또는 null |

한쪽 이상의 제한이 필요하며 둘 다 있으면 minimum <= maximum이어야 합니다.
외부 네트워크용으로 1을 넘는 제한도 허용하지만 수동성을 인정한다는 뜻은 아닙니다.
양 끝점과 그 사이에 저장된 주파수만 선택합니다. 숨은 보간·외삽·자동 세분·연속
대역 최악값 계산은 하지 않으며 표본 사이 공진을 놓치지 않는다고 보장하지 않습니다.

`db_to_magnitude(dB)`는 10**(dB/20)을 계산하고 비유한 값이나 표현 불가능한
제한을 거부합니다. 삽입손실 <=3dB는 **minimum** 10**(-3/20), 반사손실 >=20dB는
반사 항의 **maximum** 10**(-20/20)을 지정합니다. 누화·모드 변환도 상한을
사용합니다. power-normalized S의 진폭 dB이며 서로 다른 기준 임피던스에서도
원시 전압 비율을 뜻하지 않습니다.

각 검사는 선택 주파수·크기·부호 있는 여유를 모두 보존합니다. 여유는
magnitude-minimum 또는 maximum-magnitude이고, 양쪽 제한이면 그중 작은 값입니다.
숨은 허용오차 없이 모든 여유가 0 이상일 때만 통과합니다. `failed_indices`는
선택 주파수 배열의 인덱스, `worst_index`는 최소 여유의 첫 인덱스입니다.
정확한 0은 유한한 크기로 보존하며 dB 바닥값으로 자르지 않습니다. 전체 여유는
모든 검사의 최솟값입니다. 0 상한은 수치 반올림 때문에 실패할 수 있으므로
필요한 수치 여유를 제한에 명시해야 합니다.

`assess_band(LineNetwork, limits)`는 기존 네트워크에 같은 검사를 적용합니다.
저장 결과는 원래 입력과 선택적 필드 추출도 보존합니다. 공통 실행은 유한한
검사 결과와 기준/포트 정보를 내보냅니다. `status='complete'`는 계산 완료이며
제한 만족 여부는 별도 `result.passed`입니다. 제한 위반은 솔버 실패가 아닙니다.

25Ω 직렬저항(50Ω 기준 S21=.8, S11=.2), 방향이 다른 S 항, 0과 경계값,
명시 혼합모드, 조립·변환·Touchstone 재생, 실제 필드 입력 연결을 검증합니다.
정합 무왜곡 선로는 exp(-alpha*length) 및 독립 scikit-rf 2.2.0
`DefinedGammaZ0`와 1e−10 기준으로 대조합니다. 새 필드 이산화는 없으며 기존
메시·외곽·재료·실측 유효범위 제한이 유지됩니다.

```sh
python -m pytest -q tests/sipi/test_band.py tests/sipi/test_network_document.py tests/sipi/test_network_assembly.py tests/sipi/test_lumped_network.py tests/sipi/test_execution.py
```
