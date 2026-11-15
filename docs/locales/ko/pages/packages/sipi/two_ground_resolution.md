# 양면 접지 선로의 유한 해상도 평가

[English](../../../../../packages/sipi/two_ground_resolution.md)

`assess_two_ground_line_resolution`은 [양면 선로](two_ground_panel_line.md)의
유전체 메시, 전류 패널, 외곽 폭을 나누어 비교합니다.
`TwoGroundResolutionDocument`는 같은 요청을 엄격한
`sipi.two-ground-resolution/1` JSON으로 저장합니다. 계산이 완료되어도 기준을
넘으면 미수락이며, 유한한 두 결과의 일치는 절대 정확도나 오차 보증이 아닙니다.

영문 예제는 풀이 없이 2층 편심 단선과 명시 입력 여섯 개를 준비합니다.
`request.analyze(max_evaluations=6)`가 base, volume, panel, joint와 두 outer를
계산합니다. 직접 API도 같은 제어 인자를 사용합니다. max_solves는 내부 선형계
수가 아닌 전체 선로 계산 시도 수입니다. 모든 계획과 host 예산을 먼저 검증합니다.

volume은 edge_size/far_size/grade만 지정 비율로 줄입니다. 패널 세 제어값을
모두 지정해야 하며 감소할 수 없고 적어도 하나는 증가해야 합니다. outer는
joint의 체적/패널 설정을 유지하되 넓은 영역에 맞춰 ground_modes를 늘릴 수
있습니다. 옆 경계만 넓히고 실제 접지 평면, 도체, 내부 경계면, 재료 법칙,
주파수 순서, 선로 길이와 기준 임피던스는 보존합니다. 열린 옆 경계는 이 모델의
유한영역 수직 플럭스 0 조건이며 방사 경계가 아닙니다. 외곽 자동 선택이나
재시도, 입력 자르기, 계산법 대체는 없습니다.

선택한 R, 내부/외부 L, C, G, C0의 모든 행렬 원소와 주파수를
absolute + relative*max(abs(a),abs(b))와 비교합니다. 단위는 SI이고 작은
원소를 위한 분모 바닥값이 없습니다. volume/panel은 base와, joint는 각 단일
세분 결과와, 모든 outer는 joint와 비교합니다. 저장 한계 키는 R_ohm_per_m,
L_internal_h_per_m, L_external_h_per_m, C_f_per_m, G_s_per_m, C0_f_per_m이며
relative/absolute를 명시합니다. 선택하지 않은 양은 평가하지 않습니다.
각 차이와 허용값, 정확 입력, 전류 근거와 실제 유전체 메시 식별자를 보존합니다.

풀이 또는 비교 예외가 나면 이후 계산을 멈추고 이전 완료 결과·실패 단계와
입력을 남깁니다. typed 전류/메시 실패는 원 원인 정보를 보존하며 중단 신호는
전파합니다. 공통 실행에서 수치 불일치는 complete/accepted=false이고 예외는
failed와 부분 결과입니다. 부분 실패를 저장하려면 SavedExecutionRecord에
`sipi.execution-record/2`를 명시합니다. 기본 version1은 계속 거부합니다.
version2는 새 입력의 원래 계획 순서·입력과 typed 실패 연결을 풀이 없이
확인합니다. 구조 검사와 digest는 물리 결과의 진위를 보증하지 않습니다.
record/project 재열기는 계산하지 않습니다.

검증은 독립 원소별 비교, 모든 실패 위치, 변경된 물리 입력과 부족 예산 거부,
손상 기록 거부, 기존 해상도 회귀를 포함합니다. 사전 등록 실물은 예제의 여섯
선로·2/5GHz·여섯 행렬량 모두 relative .01/absolute 0입니다. 소스와 정확
설치본에서 대조합니다. 이 유한 단선 사례는 모든 쌍/제조 단면의 수렴이나
점근 수렴, 실측 손실 정확도, 다른 플랫폼 동작을 보증하지 않습니다.

## 등록된 쌍 선로 검사

추가 유한 사례 세 개는 기존 폭8mm의 대칭·좁은 간격·비대칭 쌍 입력과
보관된 독립 P4 참조를 사용합니다. 양 접지 평면, 서로 다른 신호 금속과
positive 신호의 명시 코팅을 보존합니다. 2/5GHz에서 패널64/128,
ground_modes128/256, 별도 절반 체적 메시와 폭16/32mm의 modes512/1024를
비교합니다. 비대칭은 기존 degree14, 나머지는 degree12입니다. 여섯 양의
모든 원소에 모든 비교축에서 상대.01/절대0을 요구합니다.

각 실제 선로는 균일매질 불변식과 독립 행렬지수 포트 파동 변환으로도
검사합니다. joint는 기존 P4 정전용량5e-4, 저항·내부 인덕턴스.01 허용값과
비교하며 절대 바닥값을 두지 않습니다. 대칭 넓은 상자는 보관된 P4 참조를
사용하지만16/32mm 참조는 coarse이므로 새 참조 수렴의 증거는 아닙니다.
기존 참조 배열·fixture·허용값은 바꾸지 않습니다. 모든 입력/전류/메시/비교
기록을 assertion 전에 남깁니다. 이 유한 묶음은 모든 쌍 기하, 연속 주파수
대역이나 실측 정확도 검증을 뜻하지 않습니다.
