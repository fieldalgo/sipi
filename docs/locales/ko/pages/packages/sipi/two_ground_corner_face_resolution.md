# 모서리 전류 전송선의 유한 해상도 비교

`sipi.two_ground_corner_face_resolution`의
`assess_two_ground_corner_face_line_resolution`은 명시적으로 입력한
[모서리 면별 전송선](two_ground_corner_face_panel_line.md)을 비교합니다.
기존 선로·해상도 방식 및 저장 스키마는 변경하지 않습니다.

선로, 세 설정 모두를 담은 `refined_panel_options`, 하나 이상의 명시
`outer_documents`, 비어 있지 않은 `tolerances`를 제공합니다. 비교량은
`R`, `L_internal`, `L_external`, `C`, `G`, `C0` 중 선택하며 각각
`ResolutionTolerance(relative, absolute)`를 사용합니다. absolute는 SI입니다.
기본 수치 허용오차는 없습니다. `refinement_factor` 기본값은 0.5,
`max_solves`는 6이며 허용 범위는 5–16입니다.

기준, 유전체 메시만 세분, 전류 패널만 세분, 두 축 동시 세분, 각 외곽
확장 선로를 계산합니다. 메시의 명시 edge_size/far_size/grade에 세분 계수를
곱합니다. 패널 설정은 줄일 수 없고 하나 이상 증가해야 하며 보간 차수는
지원하는 24로 유지합니다. 외곽 선로는 동시 세분의 메시·분할 수를 유지하고
접지 모드 수만 늘릴 수 있습니다. 폭은 증가해야 하며 물리적 위·아래 접지면,
도체·유전체 경계·금속 법칙·주파수·길이·포트는 그대로여야 합니다.
모든 계획 입력과 전체 선로 계산 예산을 필드 계산 전에 검사합니다.

비교는 유전체/기준, 패널/기준, 동시/유전체, 동시/패널, 각 외곽/동시입니다.
각 주파수의 선택 행렬 원소 모두에
`abs(new-old) <= absolute + relative*max(abs(new), abs(old))`를 적용합니다.
상대 분모 바닥값을 넣지 않으며 허용량이 0이면 정확한 일치를 요구합니다.
작은 상호 항도 제외하지 않습니다. 선택하지 않은 양은 평가하지 않습니다.
예산은 내부 선형계 횟수가 아닌 전체 선로 평가 횟수입니다.

불변 결과는 입력, 독립 세분 축, 전류 설정, 실제 메시, 차이와 허용량을
보존합니다. 계산이 끝났어도 불일치하면 `completed=True, accepted=False`입니다.
선로 실패 시 이전 완료 계산과 해당 전류/메시 오류를 남기고 후속 계산을
멈춥니다. 비교 단계 실패라면 직전 완료 선로도 보존합니다. 사용자 중단은
일반 실패로 바꾸지 않습니다. 기록 scope는
`two-ground-corner-face-finite-resolution-not-absolute-accuracy`입니다.
저장 해상도 스키마·자동 세분·역산·제조 공차 수락을 새로 연결하지 않습니다.

유한 차이 일치는 필요한 관측이며 절대 오차 추정·점근 수렴·실측 동박 검증을
뜻하지 않습니다. 선로 기본 해상도만으로 일치를 보장하지 않습니다. 독립 전류·
네트워크 참조와 함께 판단해야 하며 실패를 다른 기하의 통과나 허용량 완화로
대체하지 않습니다.

## 비교 입력 저장

별도 [저장 비교 문서](two_ground_corner_face_resolution_document.md)는 명시 설정·유한 불일치·부분 실패 근거를 공통 저장 실행과 프로젝트에 보존합니다.
