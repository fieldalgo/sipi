# 이름을 지정한 포트 연결과 이상적인 분기점

`connect_networks(left, right, connections)`는 두 single-ended `LineNetwork`의
포트를 명시적으로 연결합니다. 각 쌍은 `(왼쪽_이름, 오른쪽_이름)`이고 포트마다
한 번만 연결할 수 있습니다. 연결 한 개 이상과 외부 포트 한 개 이상이 필요합니다.
이름이나 near/far 순서에서 배선을 추정하지 않습니다.

주파수 배열과 연결되는 포트의 양의 실수 기준 임피던스가 **정확히** 같아야 합니다.
필요하면 먼저 `renormalized(...)`를 명시적으로 호출합니다. 출력은 왼쪽 잔여 포트
다음 오른쪽 잔여 포트 순서이며 각 기준 임피던스를 보존합니다. 이름이 겹치면
출력 `port_names=[...]`를 지정합니다. 입력은 바뀌지 않고 결과 배열은 읽기 전용입니다.
혼합 모드, 같은 네트워크 내부 연결, 주파수 보간, 자동 기준 변경은 지원하지 않습니다.

`ideal_junction(frequency, port_names=[...], z_ref=...)`는 두 개 이상 단자를 갖는
길이 0의 노드입니다. 단자는 같은 전기적 접지를 공유하고 전압이 같으며 노드로
들어오는 전류의 합이 0입니다. 기준 임피던스는 서로 달라도 됩니다.
`uᵢ=(1/sqrt(Zᵢ))/sqrt(sum(1/Z))`일 때 실수 대칭 산란행렬은 `S=2uuᵀ−I`입니다.
상호적이고 무손실이지만, 같은 기준의 세 포트 이상 분기점은 각 포트에서
**정합되지 않습니다**.

## 예: 1차원 개방 병렬 스텁

```python
from sipi import ideal_junction, connect_networks, rlgc_network, terminate_ports

frequency = [0, 1e9, 5e9, 10e9]
junction = ideal_junction(frequency, port_names=['input', 'output', 'branch'])
stub = rlgc_network(
    frequency, R=[[0]], L=[[250e-9]], G=[[0]], C=[[100e-12]],
    length=.01, z_ref=50, names=['stub'],
)
joined = connect_networks(junction, stub, [('branch', 'near:stub')])
result = terminate_ports(joined, {'far:stub': 'open'})
touchstone_text = result.touchstone()
```

출력 포트는 `input`, `output`입니다. 속도 2e8 m/s인 1 cm 개방 스텁은 5 GHz에서
병렬 단락, 10 GHz에서 병렬 개방이 됩니다. 종단을 `'short'`로 바꾸면 극한이
반대가 됩니다. 유한 수동 복소 부하는 기존 `terminate_ports` 계약을 사용합니다.
스텁 끝을 먼저 종단 처리한 뒤 연결해도 같은 회로입니다.

이상적인 분기점은 실제 기생 성분·지연·방사·패드·비아·귀환 전류 전이 모델을
추가하지 않습니다. **1차원 선로 회로**이며 3차원 비아/스텁 전계 해석이 아닙니다.
선로 파라미터의 재료 및 준TEM 유효 범위 안에서 사용해야 합니다.

## 수치 계약과 검증

입력 산란행렬을 블록 대각으로 합치고 내부 출력 파동을 상대방 입력으로 교환하여
`(I−P Sii)ai = P Sie ae`를 풉니다. S를 역행렬로 만들지 않습니다. 피드백 조건수는
`1e12` 이하, 정규화 재구성 잔차는 `1e-10` 이하이어야 합니다. 특이 루프,
비유한/표현 불가능한 출력, 맞지 않는 메타데이터를 정규화 없이 거부합니다.
이 검사는 물리 정확도나 측정 잡음 보정을 보장하지 않습니다. 임의 입력 S의
수동성도 추정하지 않습니다.

서로 다른 기준의 분기점과 동시 교차 연결을 scikit-rf 2.2.0의
splitter/connect/innerconnect와 비교하며 최대 절대 S 차이 기준은 `1e-10`입니다.
KCL·공통 전압·상호성·유니터리성·연결한 노드의 동등성·개방/단락 스텁 닫힌 해는
`1e-12`입니다. 스텁은 여러 임피던스에서 DC·1/4파장·1/2파장을 검사합니다.
손실 선로의 유한 복소 부하는 해석적 입력 어드미턴스와 독립 연결 계산으로
검사합니다. near/far 연결은 기존 cascade 및 선로 길이 합산을 재현합니다.
포트 순서·기준·읽기 전용 사본·잘못된 배선·특이/나쁜 조건수·부동소수점 넘침도
검사합니다. 이는 회로 행렬 검증이며 FEM 메시 수렴이나 실측 기판 검증이 아닙니다.

Python 함수는 기존 저장형 선로 입력의 네트워크를 받아 Touchstone을 만들 수
있습니다. 이름 배선과 이상적인 노드의 저장형 조립 스키마는 아직 없으며
`NetworkTransformDocument`는 기존 문서에 명시된 연산만 지원합니다.

[near/far 연결](connection.md) · [포트 부하](port_reduction.md) ·
[네트워크 모델](network.md) · [English](../../../../../packages/sipi/named_connections.md)
