# 선형 모서리 밀도·면별 금속 전송선 저장

`sipi.two_ground_linear_corner_face_panel_line`의
`TwoGroundLinearCornerFacePanelTransmissionLineDocument`는 별도 스키마
`sipi.two-ground-linear-corner-face-panel-transmission-line/1`을 사용합니다.
[선형 모서리 밀도 전류](two_ground_linear_corner_conductor.md), 기존 면별 금속
법칙, 동일 단면의 유전체 계산과 다도체 RLGC 네트워크를 연결합니다.
기존 스키마·기본값을 유지하고 옛 입력의 정규화가 새 방법을 자동 선택하지
않습니다.

`CrossSectionDocument`에는 유한 직사각형·사다리꼴 Trace 신호1–2개,
위·아래 접지와 열린 측면을 지정합니다. 각 신호는 bottom/top/left/right
금속을, reference는 위·아래 접지박, `sides: null`, 빈 `conductors`를
갖습니다. 코팅·거칠기·잔여 금속 코어·재료 소유권·표피 깊이의 기존 제한을
유지합니다. 단위는 SI, 위상 관례는 `exp(+j omega t)`입니다.

생성자 입력은 `cross_section`, `frequency`, `materials`, `conductors`,
`reference`, `ground_thickness`, `length`, `z_ref` 및 패널 설정입니다.
기본 분할32, 실제 미세 접지 모드256, 보간 차수24입니다. 실제 한 변 패널
수는 분할보다6개 적고 패널마다 밀도 모드2개를 갖습니다. 공유 엔진을 조회하기
전에 총512개 물리 패널 예산을 검사하므로 Trace 한 개는 최대134, 두 개는
최대70 분할이며 두 경우 모두32→64 세분이 가능합니다. 분할과 모드는
짝수이고 접지 모드는64–4096이며 절반 모드와 비교합니다. 자원이 부족하면
거친 계산으로 우회하지 않습니다.

`dumps`·`loads`·`from_dict`·`to_dict`는 분리된 엄격 JSON을 보존합니다.
정규화는 필드 풀이 없이 입력을 검사합니다. `analyze()`는 R/L/G/C,
네트워크, 정확한 입력, 실제 재사용 유전체 메시 및 불변 전류 설정을
보존합니다. 저장 요청·프로젝트·실행 기록·CLI는 같은 문서와 주파수 예산,
계산 경로를 사용합니다. 가져온 기록의 아티팩트 해시는 설치 파일의 증명이
아닙니다.

`current_record()`의 종류는 `two-ground-linear-corner-power-faces-all-active`,
내부 전체 전류 기록은 `two-ground-linear-corner-power-all-active`입니다.
진공 활성 전류 인자를 그대로 유지하고 유전체 층은 동일 기하의 C/G에
반영합니다. 전류 모델은 균질 자기장 외부 영역의 근사이며 내부 인덕턴스는
외부 인덕턴스에 한 번만 더합니다.

`TwoGroundLinearCornerFacePanelLineError`는 전류·메시·유전체·네트워크의
실패 단계, 원인, 정확한 입력과 완료된 부분 작업을 보존합니다. 저장 실행은
부분 결과를 완료로 표시하지 않습니다. 기존 해상도·목표·제조 공차 스키마는
새 엔진을 자동 선택하지 않으며 명시적인 연결은 별도 작업입니다.

균일 C/G·역인덕턴스 항등식, 독립 V/I 전파, 수동성, 동일 이종 유전체 C/G와
메시, 직접 면별 손실, 필드 없는 입력 검사, typed 실패 및 실제 저장·CLI·
프로젝트 재실행을 검사합니다. 전류장의 수렴·해석해·기준 대조 근거는 정확한
공유 엔진과 어댑터의 범위를 따릅니다. 접지 가드·임의 기하·유전체 경계
모서리·실물 쿠폰·브라우저·다른 플랫폼 지원의 근거로 확대하지 않습니다.

[English](../../../../../packages/sipi/two_ground_linear_corner_face_panel_line.md)

명시적 [유한 해상도 경로](two_ground_linear_corner_face_resolution.md)는 전류·체적·측면 폭을 근거와 함께 비교합니다.

## 유계 역산

[직접 선형 전류 역산](two_ground_linear_corner_face_line_goal.md)은 변수 하나를 찾고 입력을 고정한 유전체·패널·공동 세분 검사를 각각 수행합니다.

## 제조 입력 표본

[선형 전류 계산량 study](two_ground_linear_corner_face_line_study.md)는 명시적인 물리 면별 법칙과 함께 모든 표본·실패 행·기술 통계를 보존합니다.
