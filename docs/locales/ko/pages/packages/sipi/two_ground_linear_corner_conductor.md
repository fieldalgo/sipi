# 선형 모서리 밀도 전류

[English](../../../../../packages/sipi/two_ground_linear_corner_conductor.md)

`two_ground_linear_corner_conductor`는 정확한 개발 버전 `galerkin`의 패널당
두 밀도 모드를 사용하는 모서리 전류 엔진을 명시적으로 선택합니다.
접지된 위·아래 평면 사이의 직사각형·사다리꼴 `Trace` 신호선 한 개 또는
두 개를 지원하며 측면은 열려 있습니다. 접지 트레이스와 일반 다각형은
거부합니다. 균질 진공에서 자기장 외부 영역의 전류를 추출하므로 유전체
메타데이터는 이 전류 인자를 바꾸지 않습니다. 유전체 경계 모서리나
유한 금속 내부 확산을 푸는 기능은 아닙니다.

```python
from sipi.two_ground_linear_corner_conductor import (
    two_ground_linear_corner_face_current_factors,
)

factors = two_ground_linear_corner_face_current_factors(
    section, panels_per_edge=32, ground_modes=256, interpolation_degree=24,
)
```

단면 길이 단위는 m입니다. 각 Trace의 아래·위·왼쪽·오른쪽 면 뒤에 아래·위
접지박이 이어집니다. 적분 전류는 단위 신호 전류에 대한 부호 있는 무차원
값, 전류 제곱 적분 인자는 `1/m`, 진공 정전용량 `C0`는 `F/m`입니다.
불변 배열과 `two-ground-linear-corner-power-all-active` 진단값을 보존하며,
공유 엔진의 활성 전류 인자를 별도 기저 합동 변환 없이 그대로 사용합니다.

각 변은 `panels_per_edge - 6`개 물리 패널로 구성되고, 패널마다 질량이
있는 상수 모드와 질량이 0인 선형 모서리 밀도 모드가 있습니다. 분할 수는
16 이상 짝수이며 물리 패널 상한 512개 때문에 Trace 한 개에서는 최대134,
두 개에서는 최대70입니다. 기본32에서64로 세분하는 것은 둘 다 가능합니다.
공유 엔진을 조회하기 전에 이 예산을 검사합니다. 접지 모드는64–4096의
짝수, 보간 차수는24로 고정하며 실패 시 다른 설정으로 우회하지 않습니다.
수치 잔차, 전류 보존, 물리적 면 분할의 기존 기준을 유지합니다.

전체 경계 인자는 `two_ground_linear_corner_current_factors`로 얻습니다.
`two_ground_linear_corner_conductor_loss`와
`two_ground_linear_corner_conductor_loss_by_face`는 기존 전체·면별 표면 금속
법칙을 재사용합니다. 재료, 주파수, 남은 코어 및 접지박 두께 검사는 전계
풀이 전에 실행됩니다. 저항은 `ohm/m`, 내부 인덕턴스는 `H/m`이며 표면
섭동 추정입니다. 코팅·거칠기의 기존 유효 범위를 유지하고 미세 거칠기나
코팅 모서리를 직접 해석하지 않습니다.

직접 API만 추가하며 기존 기본 엔진, 저장 JSON, 해상도·목표·공차 문서와
브라우저 실행은 바꾸지 않습니다. 기존 [모서리 전류](two_ground_corner_conductor.md)를
계속 사용할 수 있습니다. 공개되지 않은 공유 API는 버전 문자열만으로
식별할 수 없으므로 [정확한 아티팩트 설정](../../../../../development.ko.md)을 사용합니다.

물리적 면 대응, 공유 엔진과 제품 전류의 일치, 실제 단일·쌍 선로의 패널
세분, 독립 표면 임피던스 주파수 법칙, 소모 전력, 상호적 수동 네트워크,
불변 출력 및 입력 거부 순서를 검증합니다. 공유 엔진은 해석적 모멘트,
원형 도체 극한, 등록한 P3 대조와 외곽 변화도 별도로 검사합니다. 유한
해상도 간 일치는 절대 정확도·실측 검증·다른 플랫폼·2D 전체 완성을
뜻하지 않습니다. 설계에 사용하는 각 양에 대해 패널과 외곽을 독립적으로
세분해 확인해야 합니다.

별도 [저장 면별 전송선](two_ground_linear_corner_face_panel_line.md)은 이 명시적 전류 방법을 동일 기하 유전체와 실행 재생에 연결합니다.

별도 [세 활성 도체 조화기저 전류 어댑터](two_ground_harmonic_three_active_corner_conductor.md)는 고유 입력 범위·물리 패널 한도·방법 식별을 유지한다.
