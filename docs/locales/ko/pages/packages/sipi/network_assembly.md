# 네트워크 조립 입력 저장

`NetworkAssemblyDocument`는 시작 구성 요소와 새 구성 요소를 잇는 연결 순서를
저장합니다. [이름 지정 배선과 이상적인 분기점](named_connections.md), 기존 선로
추출, 명시 네트워크 입력의 엄격한 계약을 재사용합니다.

```python
from sipi import NetworkAssemblyDocument, NetworkTransformDocument

frequency = [0, 1e9, 5e9, 10e9]
node = dict(kind='ideal-junction', frequency_hz=frequency,
            port_names=['input', 'output', 'branch'], reference_ohms=50)
stub = dict(kind='rlgc', frequency_hz=frequency,
            R=[[0]], L=[[250e-9]], G=[[0]], C=[[100e-12]],
            length_m=.01, reference_ohms=50, names=['stub'])
assembly = NetworkAssemblyDocument(node, connections=[
    dict(network=stub, ports=[['branch', 'near:stub']]),
])
loaded = NetworkTransformDocument(
    dict(kind='network-assembly', document=assembly.to_dict()),
    operations=[dict(kind='terminate-ports', loads={'far:stub': 'open'})],
)
result = NetworkTransformDocument.loads(loaded.dumps()).analyze()
```

결과는 1 cm 개방 병렬 스텁이 연결된 input/output 네트워크입니다.

## 계약

`sipi.network-assembly/1` 스키마의 필드는 schema·network·connections뿐입니다.
구성 요소는 기존 rlgc·인라인 touchstone·transmission-line·volume-line
[네트워크 입력](circuit_document.md), 또는 ideal-junction입니다. 분기점의 필드는
kind·frequency_hz·port_names·reference_ohms이며 두 개 이상의 고유 이름 배열이
필요합니다. 양의 실수 기준은 scalar 또는 포트별 배열이고 전체 배열로 저장합니다.
구성 요소 안에 조립이나 변환을 다시 넣지 못합니다. 파일 경로·URL·표현식·자동
기하 추정·재귀 계획은 없습니다.

connections는 1–32개 객체입니다. 각각 새 구성 요소 network와 비어 있지 않은
ports 배열을 요구합니다. 각 쌍은 `[현재_포트, 새_구성요소_포트]`입니다. 선택 필드
port_names는 남은 출력 **전체**의 이름을 지정합니다. 포트를 두 쌍에서 재사용할
수 없고 매 연결 후 외부 포트가 하나 이상 남아야 합니다. 현재 포트는 앞선 모든
연결의 출력이므로 이미 소비한 이름을 재사용할 수 없습니다.

출력 순서는 현재 잔여 포트 다음 새 구성 요소의 잔여 포트입니다. 기본값을 포함한
전체 출력 이름 배열을 정규 JSON에 저장합니다. 기본 이름이 겹치면 명시해야 합니다.
이는 순서가 있는 네트워크 구성이지, 이름 자동 연결이나 전역 netlist 추론이 아닙니다.

주파수 배열과 각 연결 쌍의 양의 실수 기준 임피던스가 정확히 같아야 합니다.
자동 보간·기준 변경은 없습니다. 잘못된 배선·기준·최종 회로 포트는 메시 생성 전에
실패합니다. 명시 RLGC·Touchstone parsing은 수치 네트워크를 구성할 수 있습니다.
중복 JSON 키·미등록/누락 필드·미지원 버전·비유한 수치·bool 수치를 거부합니다.
입력은 복사하고 to_dict는 새 맵, frequency·z_ref는 읽기 전용 사본,
port_names는 최종 tuple입니다. 개발판은 정확한 커밋과 wheel hash도 기록하세요.

analyze는 호출마다 각 기하 구성 요소를 한 번 추출하고 기존 연결 솔버를 적용합니다.
결과에는 network·정규 input_json·source_networks tuple·extractions tuple이
있습니다. 순서는 시작 구성 요소 다음 각 추가 구성 요소입니다. 명시 네트워크와
분기점의 extraction은 None, 기하 입력은 원래 진단 결과입니다. 실패를 부분 조립
성공으로 바꾸거나 수치/모델 기준을 변경하지 않습니다.

CircuitDocument와 NetworkTransformDocument 모두
`{"kind":"network-assembly", "document":assembly.to_dict()}`를 받습니다.
조립 후 포트 축약·기준 변경을 하고 기존 회로로 구동할 수 있습니다. 반대로 조립
구성 요소로 변환 결과를 넣는 것은 지원하지 않습니다. 회로 결과 extraction에
조립 또는 조립을 포함한 변환 결과가 남습니다. 이전 판독기는 새 kind를 거부합니다.
기존 스키마 필드의 의미는 유지하며, 결과 영구 저장 형식이 아닌 입력 형식입니다.

## 검증과 한계

저장형 개방/단락 스텁의 구동 전압·전류를 DC·1/4파장·1/2파장 해석해와 절대
1e-12로 비교합니다. 유한 복소 부하를 단 두 스텁 회로는 scikit-rf 2.2.0의 독립
이상 선로·연결과 최대 절대 S 오차 1e-10으로 비교합니다. 교차 Touchstone 연결,
이름 지정, 사본, 32/33회 제한, 잘못된 메타데이터, 특이 해석, 정확 JSON 재현도
검사합니다. 두 기하 입력 종류 모두 parsing 메시 0번, 해석 시 구성 요소마다
메시 1번과 진단 보존을 확인합니다.

기존 모델의 조합 검증입니다. 이상적인 노드는 실제 접속부·비아·패드·3차원 스텁
전이의 기생 성분을 추가하지 않습니다. 기초 선로의 재료·준TEM 한계와 연결 조건수
검사를 유지합니다. 추가 실측 기판·시간영역·FEM 메시 수렴·새 플랫폼 검증을
주장하지 않습니다.

[변환](network_document.md) · [구동 회로](circuit_document.md) ·
[English](../../../../../packages/sipi/network_assembly.md)
