# 모서리 전송선 유한 비교 저장

`sipi.two_ground_corner_face_resolution_document`의
`TwoGroundCornerFaceResolutionDocument`는 별도 스키마
`sipi.two-ground-corner-face-resolution/1`을 사용합니다. 명시적인
[유한 모서리 비교](two_ground_corner_face_resolution.md)를 저장하며
기존 선로·해상도·실행 기록 형식의 의미는 유지합니다.

모서리 면별 선로와 `refined_panel_options`, `outer_documents`,
`tolerances`, `refinement_factor`, `max_solves`를 제공합니다.
마지막 두 설정의 기본값은 0.5와 6이며 수치 허용량에는 기본값이 없습니다.
JSON 키는 `schema`, `line`, `refined_panel`, `outer_lines`,
`refinement_factor`, `max_solves`, `tolerances`입니다. 허용량에는 SI 양의
이름과 명시 `relative`/`absolute`를 사용합니다. 각 선로의 전류·유전체 메시
설정을 그대로 저장합니다. 누락·추가 키, 중복 JSON 키, 비유한 값 및
물리적 조건을 바꾼 외곽 확장 계획은 거부합니다.

정규화·요청 준비·프로젝트 재열기·결과 기록 로딩은 필드를 계산하지 않습니다.
`analyze(max_evaluations=...)`와 공통 저장 실행은 전체 선로 평가 예산을
계산 전에 검사합니다. 선택 비교 축과 실제 입력을 보존하며 예산이나 허용량을
자동 변경하지 않습니다.

`normalize_saved`, `execute_saved`, `SavedExecutionRequest`, CLI와
`SavedProject`가 같은 계약을 사용합니다. 계산이 완료되어도 수치가 일치하지
않으면 `accepted=False`입니다. 실패하면 완료된 평가·전류·메시 및 실패한
계획 입력을 남깁니다. 부분 결과를 포함하는 실패는
`SavedExecutionRecord(..., schema='sipi.execution-record/2')`로 보존하며
버전 1은 기존대로 비어 있지 않은 실패 결과를 거부합니다. 복원할 때 typed
원인, 계획 횟수, 정확한 입력 순서와 실패 단계를 검사합니다.
이 형식은 구조 검사이며 서명·선언한 파일의 실제 실행 증명·물리적 정확도
검증을 대신하지 않습니다.

시험은 엄격한 무계산 정규화, 예산 거부, 실제 저장 실행, 완료 불일치,
각 단계 실패·중단, 기록/프로젝트 재열기 및 부분 근거 변조 거부를 확인합니다.
원소별 유한 일치는 절대 오차 범위·일반 수렴·물리 보정·새 운영체제 지원을
뜻하지 않습니다. 기존 스키마가 이 전류 방식을 자동 선택하지 않습니다.
