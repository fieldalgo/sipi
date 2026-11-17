# 세 활성 도체의 코너 조화기저 면 전류 저장 선로

`sipi.two_ground_harmonic_three_active_corner_face_panel_line`의
`TwoGroundHarmonicThreeActiveCornerFacePanelTransmissionLineDocument`는 별도
`sipi.two-ground-harmonic-three-active-corner-face-panel-transmission-line/1`
스키마를 사용한다. [세 활성 도체 전류](two_ground_harmonic_three_active_corner_conductor.md),
기존 면별 표면 금속 법칙, 같은 단면의 유전체 전계와 결합 RLGC·6포트 망을 연결한다.
기존 입력·기본값은 바꾸지 않고 방법을 자동 전환하지 않는다.

단면에는 정확히 세 개의 유한 직사각형/사다리꼴 Trace 신호, 위아래 접지와 열린
측벽이 있어야 한다. 내부 접지 Trace는 지원하지 않는다. 신호의 아래·위·좌우 면과
두 기준박의 법칙을 명시하고 reference의 sides는 null, conductors는 빈 객체다.
코팅·거칠기·잔존 코어·재료 소유·표피깊이 제한을 유지한다. SI단위와
`exp(+j omega t)` convention을 유지한다.

생성자 입력은 cross_section, frequency, materials, conductors, reference,
ground_thickness, length, z_ref 및 panel 제어다. 기본 분할32·실제 fine접지모드256·
보간차수24이며 각 변의 물리 패널은 분할수보다6개 적고 패널마다 공간 모드2개다.
물리 패널512개 한도를 공유 솔버 조회 전에 검사한다. Trace 세 개의 최대 분할은48로,
32→48 세분이 같은 한도 안에 있다. 접지모드는 짝수64..4096이며 절반 모드와 비교한다.
자원 부족을 거친 계산으로 자동 대체하지 않는다.

loads/dumps/from_dict/to_dict는 분리된 엄격한 JSON을 보존한다. 입력 정규화는
전계를 풀지 않는다. analyze 결과는 RLGC·네트워크·원본 입력·실제 유전체 메시와
불변 전류 제어를 유지한다. 요청·결과 기록·프로젝트·CLI가 같은 계산과 주파수 예산을
사용한다. 수입한 receipt에 적힌 artifact hash만으로 설치 파일 동일성이 증명되지는 않는다.

current_record의 kind는 two-ground-harmonic-corner-faces-three-active,
내부 전체 전류 kind는 two-ground-harmonic-corner-three-active다. 활성 전류 인자를
그대로 유지하고 유전체는 같은 기하의 C/G에 영향을 준다. 균일 자기 외부 근사를
유지하며 내부 인덕턴스는 외부 인덕턴스에 한 번만 더한다.

`TwoGroundHarmonicThreeActiveCornerFacePanelLineError`는 실패 단계·원인·입력과
완료된 전류/메시 작업을 남긴다. 일부 결과를 완료로 취급하지 않는다. 기존 해상도·목표·
공차 문서는 이 엔진을 자동 선택하지 않는다. 단일/차동 목표로 세 신호의 launch가
정의되지 않으므로 대각 원소나 특정 모드를 임의의 목표 임피던스로 해석하지 않는다.

균일 C/G·역 인덕턴스 항등식, 독립6차원 전압/전류 네트워크, 수동성, 비균일 유전체의
같은C/G·메시, 직접 면 손실 일치, 입력 검사, 단계별 실패 및 실제 저장/CLI 재실행을
검증한다. 전류장 수렴·독립 기준은 정확한 공유 엔진과 어댑터 근거를 따로 참조한다.
고정 접지 가드·임의 형상·유전체 경계 코너 법칙·실측 쿠폰·브라우저·다른 플랫폼의
수락을 뜻하지 않는다.

[English](../../../../../packages/sipi/two_ground_harmonic_three_active_corner_face_panel_line.md)
