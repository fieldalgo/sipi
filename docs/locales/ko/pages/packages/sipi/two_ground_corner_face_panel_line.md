# 모서리 전류·면별 금속 전송선 저장

`sipi.two_ground_corner_face_panel_line`의
`TwoGroundCornerFacePanelTransmissionLineDocument`는 별도 스키마
`sipi.two-ground-corner-face-panel-transmission-line/1`을 사용합니다.
[모서리 전류](two_ground_corner_conductor.md)를 기존 면별 금속 법칙,
동일 단면의 유전체 계산 및 다도체 RLGC 네트워크에 연결합니다.
기존 저장 스키마와 기본값은 유지합니다.

## 입력과 실행

접지된 위·아래 평면, 열린 옆 경계와 유한 두께의 직사각형 또는 사다리꼴
`Trace` 신호 1–2개를 받습니다. 접지 trace, 일반 다각형 및 신호 3개는
거부합니다. 각 신호에 bottom/top/left/right 금속을 지정하고 reference에는
위·아래 동박, `sides: null`, 빈 `conductors`를 명시합니다. 코팅·거칠기·재료
소유권·표피 깊이 기준은 기존 면별 법칙을 따릅니다. 단위는 SI,
위상 관례는 `exp(+j omega t)`입니다.

생성자는 `cross_section`, `frequency`와 키워드 `materials`, `conductors`,
`reference`, `ground_thickness`, `length`, `z_ref`, 세 panel 설정을 받습니다.
기본값은 `panels_per_edge=128`, `ground_modes=256`,
`interpolation_degree=24`입니다. 세분 수는 짝수 16–512이며 모서리 구간을
묶으므로 실제 한 변 패널 수는 6개 적습니다. ground_modes는 실제 미세 모드
수인 짝수 64–4096이고 절반 모드와 비교합니다. 보간 차수는 24로 고정합니다.
기본값만으로 임의 단면의 수렴·물리 정확도가 보장되지는 않습니다.

`dumps`/`loads`/`from_dict`/`to_dict`는 모든 설정을 엄격한 버전 JSON으로
보존합니다. 정규화는 재료·기하를 검사하며 필드 계산이나 선택적 공유 solver
조회 없이 수행됩니다. `analyze()`는 새 방법을 명시적으로 사용하며 다른
방법으로 자동 전환하지 않습니다. 공통 `normalize_saved`, `execute_saved`,
`SavedExecutionRequest`, `SavedExecutionRecord` 및 실제 재실행에 연결됩니다.
저장 기록의 호스트 artifact 선언은 설치된 파일의 검증 증거가 아닙니다.
기존 실행 주파수 예산은 필드 계산 전에 적용됩니다.

## 결과와 한계

R/L/G/C와 네트워크, 정확한 입력, 실제 유전체 메시 및 불변 전류 설정을
보존합니다. `current_record()`의 종류는
`two-ground-corner-power-faces-all-active`, 내부 whole_current의 종류는
`two-ground-corner-power-all-active`입니다. 진공 전류 기저는 직접 사용하고
유전체는 C/G에 반영됩니다. 이는 균일한 외부 자기장 표면 모델의 근사이며
유전체 경계의 모서리 법칙을 새로 구현한 것이 아닙니다. 내부 인덕턴스는
외부 인덕턴스에 한 번만 더합니다.

`TwoGroundCornerFacePanelLineError`는 실패 단계·원인·정확한 입력 및
완료된 전류/메시를 남깁니다. 공통 저장 실행도 부분 실패를 완료로 표시하지
않습니다. 기존 해상도·역산·제조 공차 스키마에는 자동 연결하지 않으며
모서리 방식의 연결은 별도 작업입니다.

선택 시험은 균일 C/G·진공 역행렬 불변식, 독립 V/I 전파 네트워크,
수동성, 동일 기하의 이종 유전체 C/G, 면별 금속 결과, 엄격 정규화,
단계별 실패 및 실제 저장 재실행을 확인합니다. 전류 정확도 근거는 adapter의
독립 P3 검증 두 기하에 한정됩니다. 임의 기하·접지 trace·실측 동박·브라우저
및 추가 운영체제의 지원을 보장하지 않습니다.

## 명시 유한 해상도 비교

별도 [유한 해상도 비교 함수](two_ground_corner_face_resolution.md)로 전류 패널·유전체 메시·옆 외곽 경계의 영향을 각 양의 명시 허용량으로 비교할 수 있습니다.
