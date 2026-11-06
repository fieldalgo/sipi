# 네트워크 변환 순서 저장

`NetworkTransformDocument`는 원본 네트워크 입력 하나와 순서가 있는 기준 임피던스
변경·수동 부하 포트 축약을 저장합니다. 기존 선로 추출·네트워크 API로 계산하며
계산 순서를 저장하는 것이 새 물리를 추가하는 것은 아닙니다.

```python
from sipi import NetworkTransformDocument
source = dict(kind='rlgc', frequency_hz=[0, 1e9, 5e9],
              R=[[0]], L=[[250e-9]], G=[[0]], C=[[100e-12]],
              length_m=.01, reference_ohms=50, names=['trace'])
plan = NetworkTransformDocument(source, operations=[
    dict(kind='renormalize', reference_ohms=[75, 120]),
    dict(kind='terminate-ports', loads={'far:trace': 'open'}),
])
result = NetworkTransformDocument.loads(plan.dumps()).analyze()
```

결과는 기준 75Ω의 near:trace 포트 하나입니다. 엄격 스키마
`sipi.network-transforms/1`의 필드는 schema·network·operations뿐입니다.
원본은 기존 [회로 네트워크 입력](circuit_document.md)의 rlgc·인라인 touchstone·
transmission-line·volume-line 중 하나이며 전체 입력과 유효성 검사를 유지합니다.
변환 문서를 다시 원본으로 넣을 수 없습니다. 재귀 계획·파일 경로·URL·표현식·
네트워크 접근은 없습니다.

operations는 실행 순서대로 1–32개 객체를 담습니다.

| kind | 추가 필수 필드 | 의미 |
|---|---|---|
| renormalize | reference_ohms | 양의 실수 scalar 또는 현재 포트 수만큼의 배열; 저장 시 전체 배열로 정규화 |
| terminate-ports | loads | 현재 포트 이름과 개방·단락·유한 수동 임피던스의 비어 있지 않은 맵; 적어도 하나는 유지 |

개방·단락은 문자열 `"open"`·`"short"`입니다. 유한 부하는 실수 또는
`{"real":..., "imag":...}`이며 두 성분 모두 scalar이거나 모두 주파수 수 F의
배열이어야 합니다. 저장 JSON은 실수 부하도 두 성분을 명시합니다. 음의 저항은
거부하며 누락한 포트는 종단하지 않습니다. 각 앞선 단계 이후의 포트 이름과
기준 배열 크기를 검사하며 자동 재정렬·보간·모델 선택·포트 대응은 없습니다.

미등록·누락 필드, 중복 JSON 키, 비유한 값, bool 수치, 미지원 버전과 잘못된
중간 포트 선택은 오류입니다. 입력·접근자 결과는 복사하며 frequency는 읽기 전용,
port_names는 최종 포트의 tuple입니다. to_dict는 새 맵을 반환합니다. parsing은
기하 메시 없이 입력 메타데이터를 검사합니다. 명시 RLGC·Touchstone의 기존 입력
검사는 수치 네트워크를 구성할 수 있습니다.

analyze는 원본을 한 번 추출한 뒤 기존 LineNetwork.renormalized와 terminate_ports를
순서대로 호출합니다. NetworkTransformResult는 network·source_network·정확한
input_json·extraction(원래 선로 결과 또는 명시 네트워크이면 None)을 보존합니다.
특이 피드백·조건수·메시·재료 오류는 그대로 전달하며 부분 성공이나 단계 생략은 없습니다.

기존 CircuitDocument에서
`network={"kind":"network-transform", "document":plan.to_dict()}`로 연결합니다.
소스·부하 이름은 최종 포트를 가리키며 제거한 이름은 추출 전에 거부합니다.
CircuitResult.extraction은 변환 결과이며 그 extraction이 원래 기하 선로 결과를
보존합니다. 기존 회로 스키마의 의미는 유지합니다. 이전 판독기는 새 kind를
거부하므로 SIPI 버전을 함께 기록하세요.

test_network_document.py는 무손실 개방·단락 선로 반사, 서로 다른 기준값을 두
유효 순서로 변환한 결과, 독립적으로 구한 구동 전압·전류를 절대 <=1e-12로 검사합니다.
비상호 Touchstone·복소 부하·반복 기준 변경은 scikit-rf 2.2.0의 renormalize/connect와
절대 <=1e-10로 비교합니다. 두 기하 입력은 메시·추출 한 번, parsing은 메시 0번을
요구하며 복사·재현·예산·오류 입력·제거한 이름·해석 실패도 검사합니다.
조합 검증이며 기하 정확도·3D 비아/stub·시간영역·GUI·새 OS 검증을 추가하지 않습니다.

[포트 축약](port_reduction.md) · [기준 변경](network.md)
