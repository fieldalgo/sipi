# 선로 연결·알려진 fixture 제거의 저장

명시적인 `sipi.network-transforms/2`는 [네트워크 변환](network_document.md)에
저장형 cascade·deembed를 추가합니다. 기존 [연결 API](connection.md)와 수치
관문을 그대로 사용합니다. 기본값인 버전 1은 옛 정규 입력을 유지하고 새 연산을
거부합니다. 옛 reader는 버전 2를 거부합니다.

```python
from sipi import LumpedNetworkDocument, NetworkTransformDocument

frequency = [0, 1e6, 1e9]
def branch(resistance, names):
    model = LumpedNetworkDocument(frequency, resistance=resistance, port_names=names)
    return dict(kind='lumped-network', document=model.to_dict())

dut = branch(7, ('near', 'far'))
fixture = branch(100, ('outside', 'inside'))
plan = NetworkTransformDocument(dut, schema='sipi.network-transforms/2', operations=[
    dict(kind='cascade', side='left', network=fixture, port_names=['input', 'output']),
    dict(kind='deembed', left=fixture, right=None, port_names=['near', 'far']),
    dict(kind='renormalize', reference_ohms=[25, 85]),
])
result = NetworkTransformDocument.loads(plan.dumps()).analyze()
assert result.network.port_names == ('near', 'far')
assert len(result.fixture_networks) == 2
assert result.fixture_extractions == (None, None)
```

## 입력 계약

두 버전 모두 schema·network·operations만 가지며 순서가 있는 1–32단계를 받습니다.
버전 2에서도 v1의 renormalize·terminate-ports를 사용할 수 있습니다.

| kind | 필수 필드 | 선택 필드 |
|---|---|---|
| cascade | side(left/right), network(fixture 입력) | port_names |
| deembed | left·right(fixture 또는 null, 적어도 하나는 비-null) | port_names |

fixture는 전체 rlgc·인라인 touchstone·transmission-line·volume-line·lumped-network
입력입니다. fixture 안에 조립이나 변환을 넣을 수 없습니다. 시작 원본은 여전히
network-assembly일 수 있습니다. 재귀 계획·파일 검색·보간·실행 입력은 없습니다.

새 연산마다 현재 네트워크와 fixture의 **2N single-ended 포트, 전체 near 다음
전체 far 순서**와 주파수 샘플이 같아야 합니다. 순서는 호출자 계약이며 이름으로
추정하지 않습니다. cascade는 도체 순서대로 왼쪽 far와 오른쪽 near를 연결하고
그 기준은 정확히 같아야 합니다. side=left는 앞, right는 뒤에 붙입니다. 기본
출력은 왼쪽 near 이름/기준 다음 오른쪽 far입니다. deembed는 알려진
left→DUT→right fixture를 제거하며 바깥 기준은 현재 양끝과 같아야 합니다.
출력 기준·기본 이름은 fixture 안쪽 포트 또는 변경 없는 현재 끝에서 가져옵니다.

port_names는 모든 출력의 비어 있지 않은 고유한 한 줄 이름입니다. 기본 이름이
겹치면 직접 지정하세요. 정규 v2 JSON은 해석된 전체 이름 배열을 저장합니다.
기준 변경은 명시적이며 **모든 앞선 단계 뒤**의 기준과 남은 이름을 추적합니다.
축소 후 홀수 포트로 fixture 연산을 수행할 수 없습니다. 마지막 단계까지의
잘못된 필드·주파수·이름·기준·포트 수는 기하 메시 전에 실패합니다. 계산된 S가
필요한 특이성·조건수는 분석 시 검사합니다. 명시 대수적/RLGC/Touchstone 입력
해석에서는 수치 네트워크를 만들 수 있습니다.

## 결과·검증·한계

frequency·z_ref는 최종 메타데이터의 읽기 전용 사본, port_names는 최종 tuple입니다.
사전은 복사됩니다. 결과는 기존 source_network·정규 input_json·원본 extraction을
유지합니다. 추가된 fixture_networks·fixture_extractions는 연산 순서이며 양쪽
제거는 left 다음 right입니다. 같은 문서도 등장마다 기록합니다. 제공 네트워크의
extraction은 None, 기하는 등장당 한 번 추출합니다. v1의 fixture tuple은 비어 있고
기존 네 인자 결과 생성자도 유효합니다. 최종 주파수·포트·기준을 메타데이터와 대조합니다.

CircuitDocument는 기존 network-transform kind로 v2를 받습니다. 소스/부하는
최종 이름을 사용하고 메시 전에 검사합니다. 변환 결과에서 fixture 진단도 확인합니다.

기존 feedback/wave-chain 조건수 상한 1e12와 잔차 관문은 유지됩니다. 50 Ω 기준의
직렬 100 Ω 저항처럼 S가 특이해도 제거 가능한 fixture가 있습니다. DC 직렬
커패시터처럼 전송이 0이면 제거할 수 없습니다. 샘플 생략·정규화 보정·수동성
복구·부분 결과 반환을 하지 않습니다. fixture 추정·측정 교정·손실/잡음 정보
복구가 아니며 수치 관문 통과는 불확도 보증이 아닙니다.

2포트 RLC 연결/제거와 비대칭 4포트 연결을 scikit-rf와 절대 S 1e-10으로 비교합니다.
해석적 저항 합·DUT 복원·부하 전압은 1e-12입니다. 두 기하 fixture 종류 모두
등장당 한 번 추출하고 진단을 보존합니다. 중간 메타데이터·옛 JSON byte 호환·
스냅샷·전송 0 실패도 검사합니다. 기하 정확도·메시/외곽 수렴은 해당 구성 요소의
책임입니다. 새 물리 모델·실측 정확도·의존성·플랫폼 지원을 추가하지 않습니다.

[English](../../../../../packages/sipi/saved_fixtures.md)
