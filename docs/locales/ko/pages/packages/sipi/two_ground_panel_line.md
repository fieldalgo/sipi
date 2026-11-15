# 양면 접지 패널 선로 저장

[English](../../../../../packages/sipi/two_ground_panel_line.md)

저장 선로 API는 `sipi.two_ground_panel_line`에
`TwoGroundPanelTransmissionLineDocument`와 엄격 스키마
`sipi.two-ground-panel-transmission-line/1`을 추가한다.
[양면 접지 표면 전류](two_ground_conductor.md)를 기존 동일 기하 유전체 추출 및
RLGC 네트워크에 연결한다. `dependencies.json`의 정확한 공유 개발 리비전이
필요하다. 저장 실행 등록은 별도이며 브라우저 검증을 뜻하지 않는다. 실행 예제는
영문 문서와 같다.

최상위 키는 schema, cross_section, frequency_hz, materials, conductors,
reference, ground_thickness_m, length_m, reference_ohms, panel이다. panel 키는
panels_per_edge, ground_modes, interpolation_degree이다. 좌표·두께·선로 길이는 m,
주파수는 Hz, 기준 임피던스는 Ω이다. 기존 CrossSectionDocument의 기하·메시와
유전체 모델 스키마를 재사용한다. 신호·접지 전체 표면 금속 JSON은 기존 명시적
벌크·거칠기·적층 도금 계약을 따른다. 누락·추가·중복·비유한 값은 거부한다.
정규화는 분리된 정규 입력을 반환하며 장 계산이나 별도 공유 기능을 요구하지 않는다.

생성 시 재료 샘플, 기하·자원 설정, 국소 표피 깊이 및 남은 코어 조건을 검사한다.
실행은 전류 계산, 정확히 같은 저장 단면의 유전체 C/G 메시, 신호 순서 확인,
기존 네트워크 구성 순서다. 전류 계산기가 진공 C0와 외부 L을 제공한다. 기존
유전체 구현은 정확히 균질인 스칼라 계수에 한해 C0를 비례 조정하며 비균질·텐서
계수는 저장 체적 메시로 푼다. 입력 기하와 수치 설정을 결과에 보존한다.
`mesh_record()`에는 실제 노드·요소·경계 집합 해시가 있다.

`TwoGroundPanelLineError`는 단계, 원인 종류, 정규 입력, 완료된 전류 결과,
완료된 유전체 메시 식별을 보존한다. 단계는 재료 입장, 도체 입장, 전류, 메시,
유전체, 네트워크다. 공유 기능 부재는 명시적인 전류 단계 실패이며 결과나 수렴을
만들어내지 않는다. 접근자로 반환한 기록은 객체와 분리되어 있다.

실제 균질 선로 6개는 단선·대칭 쌍·비대칭 쌍 각각에 공통 또는 서로 다른 접지면
금속을 넣고 2/5GHz에서 검사한다. C=epsilon_r*C0, G=omega*tan_delta*C,
L_external*C0=mu0*epsilon0*I 및 별도 구현한 행렬 지수·포트 파 변환을 확인한다.
원래 직접 전류·금속 관측 및 관련128시험도 유지한다. 별도 등록 비균질 단선 연구는
1mm씩 두 층(epsilon_r3/tan_delta.002 및 epsilon_r5/tan_delta.004), 체적 메시3단계,
최종 메시의 독립 scikit-fem 복소 P2 참조를 사용한다. 인접 C/G 및 독립 C/G의
기존1% 기준을 유지하며 통과 여부는 동반 기록에 남긴다. 적층 유전체 외곽 수렴을
대신하지 않는다.

전류 패널 수렴과 유전체 체적 메시 수렴은 서로 다른 검사다. 유한 검증은 일반
정확도·공간 비균질 자성 외부·체적 도체 확산·실측·새 플랫폼 지원을 입증하지 않는다.
기존 입력 스키마·허용치·fixture·실패 결과·기본 솔버·공개 배포·Windows
실행파일은 바꾸지 않는다.

별도 [저장 실행](two_ground_execution.md)는 host·요청·기록·CLI 전달을 추가한다.
