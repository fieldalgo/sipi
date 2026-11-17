# 고정 전위 가드가 있는 두 활성 전송선 저장 입력

`sipi.two_ground_harmonic_guard_corner_face_panel_line`의
`TwoGroundHarmonicGuardCornerFacePanelTransmissionLineDocument`는 별도 스키마
`sipi.two-ground-harmonic-guard-corner-face-panel-transmission-line/1`을 사용한다.
아래·위 접지 평면과 열린 옆 경계 안에 유한 직사각형/사다리꼴 활성 선로 두 개,
`ground=True`인 유한 가드 하나를 받는다. 가드는 0 전위에 고정한다. 부유 가드,
유한 접지 종단이나 길이 방향 비아 연결을 모델링하지 않는다.

SI 저장 입력에는 단면 문서·유전체 메시 제어, 양의 주파수, 유전체 법칙,
활성 선로별 네 면 금속, 아래/위/가드 표면 법칙, 접지 두께, 길이, 기준 임피던스,
조화기저 패널 제어가 들어간다. 가드는 전체 둘레 법칙 하나 또는 네 면 법칙을 쓴다.
정규화는 장 계산이나 선택 공유 솔버 import 없이 엄격 중첩 키, 재료·표피 깊이·
남은 코어, 기하와 자원 한도를 확인한다. 기본은32분할·256접지 모드·24차 보간이며
전류 어댑터의512개 물리 패널 한도를 유지한다.

해석은 정확히 선택한 두 전류 좌표로 진공 C0, 전체/면별 전류 및 표면 R/내부 L을
구한다. 가드 유도 전류와 손실을 보존한다. 같은 물리 단면의 메시로 비균일·분산
유전체를 포함한 C/G를 계산한다. 외부 L은 일치 C0를 사용하고 네트워크에서 내부 L을
한 번만 더한다. 두 도체 RLGC 행렬은 검증한 수동 입력에서 상호·수동4포트 망을 이룬다.
수동성 수치 검사가 실측 정확도를 보장하지 않는다.

결과는 정규 입력, 실제 유전체 메시, 명시적 패널 제어와 분리된 SI 전류 기록을 보존한다.
면 기록 kind는 `two-ground-harmonic-corner-faces-fixed-guard`, 내부 전체 기록 kind는
`two-ground-harmonic-corner-fixed-guard`다. 표면 라벨로 두 평면과 가드 각 면을 구분한다.
배열과 설정은 기존 불변 결과 계약을 유지한다. 계산 완료 자체는 패널·외곽 수렴을
뜻하지 않으며 별도 비교가 필요하다.

`normalize_saved`, `SavedExecutionRequest`, `SavedExecutionRecord`, `SavedProject`와
기존 CLI가 이 스키마를 받는다. 요청은 주파수 예산, 진단과 재실행 입력을 보존한다.
전류·메시·유전체·네트워크 실패는 형식 있는 단계, 정규 입력, 실제 끝난 작업만 남긴다.
기록을 다시 여는 일은 재계산이나 없는 결과 생성이 아니다. 기존 저장 스키마와 기본
솔버는 바꾸지 않는다.

장 없는 엄격 입력 검사·정규 왕복, 균일 C/G·역 C0 항등식, 독립 전송 상태 네트워크,
관측 메시가 같은 비균일 공개 유전체 계산 대조, 물리 금속 법칙, 실제 요청/CLI/project
재실행과 단계별 실패 기록을 검증한다. 별도 가드 어댑터·공유 장이 물리 전류 및 독립
기하 기준 근거를 보유한다. 이 스키마 자체가 목표 탐색, 공차 연구, 임의 기하,
실측 재료 검증 또는 다른 플랫폼 검증을 추가하지는 않는다.

[가드 전류 어댑터](two_ground_harmonic_guard_corner_conductor.md) ·
[English](../../../../../packages/sipi/two_ground_harmonic_guard_corner_face_panel_line.md)
