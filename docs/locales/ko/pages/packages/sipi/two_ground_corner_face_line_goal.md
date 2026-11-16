# 코너 전류 선로의 유계 역산

`sipi.two_ground_corner_face_line_goal`의
`seek_two_ground_corner_face_line_quantity`는 명시적인
`TwoGroundCornerFacePanelTransmissionLineDocument` factory를 사용하여 양수 기하 변수
하나를 역산합니다. 지원량은 `impedance_real`, `attenuation`,
`differential_forward_impedance_real`, `common_forward_impedance_real`입니다.
뒤의 두 값은 전체 전진 특성 행렬의 서로 다른 혼합 좌표 구동값이며 독립 고유모드
임피던스가 아닙니다. 양수 주파수 하나, 길이 0, 고정된 패널 설정을 사용합니다.

## 세분 검사와 유한 범위

5..10000회의 평가 예산에는 실패한 시도도 포함하며 세분 검사 세 번을 예약합니다.
선택된 입력을 고정하여 edge/far/grade만 절반, 전류 패널 수만 두 배, 둘 다 변경한
경우를 각각 풉니다. 접지 모드 수·보간 차수·물리 면별 금속법칙·주파수·신호 순서는
그대로입니다. 세분할 수 없는 입력은 장 계산 전에 거부합니다. factory 재호출,
치수 잘라내기, 대체 풀이법 사용은 하지 않습니다.

모든 세분 값은 원래 절대 목표 허용량을 만족해야 합니다. 각 값과 기준 계산의 상대
변화, 공동 세분과 각 단일 축 세분의 상대 변화는 모두 0.005 이하여야 합니다.
비교값이 0이면 0만 허용하며 분모 하한을 추가하지 않습니다. 유한 일치는 외곽 경계
검사·절대 오차 한계·설계 유일성의 증명이 아닙니다. 외곽 비교는
[별도 해상도 검사](two_ground_corner_face_resolution.md)를 사용합니다.

## 기록과 검증

선택된 정확한 문서·시도 이력·세분 입력·실제 전류와 메시 기록을 보존합니다.
형식 있는 역산 실패에는 완료 이력·실패 입력·원래 단계별 원인을 남깁니다.
사용자 인터럽트는 전파됩니다. callable을 직렬화하지 않으며 새 저장 역산·공차
schema는 이 단위에 포함하지 않습니다.

구조 시험은 네 양, 예산 예약, 모든 시도의 실패, 설정 변경, 인터럽트와 각 수락 조건을
검사합니다. 등록한 실제 단일 선로는 2 GHz에서 폭 0.55..0.65 mm로 58 Ω을 0.05 Ω
이내에서 찾으며 패널 128/256, 접지 모드 256, 차수24를 사용합니다. 모든 반환 장은
단일 선로의 `sqrt(Z/Y)`·`sqrt(Z*Y)` 항등식과 대조합니다. 명시된 사례·artifact의
검증이며 실측 포일이나 다른 플랫폼의 정확도를 확정하지 않습니다.

[English](../../../../../packages/sipi/two_ground_corner_face_line_goal.md)

## 목표 입력 저장

[별도 저장 목표](two_ground_corner_face_line_goal_document.md)는 callable을 직렬화하지 않고 입력 구간 하나·목표·예산을 이 직접 API에 연결합니다.
