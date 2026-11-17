# 세 능동 도체 유한 해상도 비교 저장

`sipi.two_ground_harmonic_three_active_corner_face_resolution_document`의
`TwoGroundHarmonicThreeActiveCornerFaceResolutionDocument`는 명시적인
[유한 해상도 비교](two_ground_harmonic_three_active_corner_face_resolution.md)를
저장합니다. 스키마는 `sipi.two-ground-harmonic-three-active-corner-face-resolution/1`입니다.
같은 여섯 단계 계산을 재사용하며 JSON 왕복이 솔버를 바꾸거나 기존 저장
선로를 다른 뜻으로 해석하지 않습니다.

기준 선로, 세 가지 전류 세분 옵션, 명시적인 외곽 선로들, 유전체 세분 배율,
선로 계산 예산과 선택한 SI 계산량의 허용량을 저장합니다. 각 허용량에는
`relative`와 `absolute`를 모두 씁니다. 분모 하한이나 묵시적인 정확도 기본값은
추가하지 않습니다. 모든 중첩 입력과 예산을 먼저 확인합니다. 세 능동 도체,
물리 접지면, 재료, 주파수, 포트, 길이는 직접 비교 계약을 따라야 합니다.

`SavedExecutionRequest` 또는 `sipi run INPUT --output RECEIPT --max-evaluations 6`로
실행합니다. 계산이 끝났어도 불일치하면 `completed=true`, `accepted=false`입니다.
완료가 유한 조건 간 일치를 뜻하지 않습니다. 형식화된 장 계산 실패는 정확한
실패 입력과 앞서 완료한 전류·메시 기록을 남기고 이후 계산을 중단하며 실패
실행 기록을 만듭니다. 사용자 중단은 그대로 전파합니다. `SavedExecutionRecord`로
저장하거나 프로젝트에 첨부할 수 있고 복원할 때 장을 다시 풀지 않습니다.
일부 실패 결과는 실행 기록 버전 2를 요구하며 계획된 단계와 완료한 입력 순서에
정확히 묶입니다.

엄격한 필드와 SI 이름, 장 계산 전 예산, 여섯 단계의 실패, 변조된 부분 기록
거부, 프로젝트 복원, CLI 전달, 직접 비교 전체 결과와 정확히 같은 실제 저장
실행을 검사합니다. 물리 예제는 등록한 상대 1%, 절대 0 기준을 유지합니다.
이는 유한 비교 기준이며 실측 또는 보편적인 정확도 인증이 아닙니다. 세 신호의
단일·차동 목표, 고정 접지 도체, UI 일치, 다른 운영체제 지원을 뜻하지 않습니다.

[English](../../../../../packages/sipi/two_ground_harmonic_three_active_corner_face_resolution_document.md)
