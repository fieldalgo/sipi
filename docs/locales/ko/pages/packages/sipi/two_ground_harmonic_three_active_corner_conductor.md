# 세 활성 도체의 코너 조화기저 전류와 표면 손실

`sipi.two_ground_harmonic_three_active_corner_conductor`는 공유 세 활성 도체
전계를 기존 표면 금속 법칙에 연결하는 명시적 모듈이다. 두 접지 평면·열린 측면
사이에 유한 직사각형 또는 사다리꼴 `Trace`가 정확히 세 개 있어야 한다. 유한
접지 도체는 받지 않는다. 기존 한두 도체 및 다른 전류 방법은 바뀌지 않는다.

함수는 `two_ground_harmonic_three_active_corner_current_factors`,
`two_ground_harmonic_three_active_corner_face_current_factors`,
`two_ground_harmonic_three_active_corner_conductor_loss`,
`two_ground_harmonic_three_active_corner_conductor_loss_by_face`다.
기존 결과 계약을 유지하여 진공 C0는 F/m, 전류 Gram은 1/m, R은 ohm/m,
내부 인덕턴스는 H/m이다. 각 신호의 아래·위·왼쪽·오른쪽 면과 두 평면의 기여를
구분한다. 전계가 이미 독립 활성 전류 기저를 사용하므로 불필요한 항등행렬 풀이나
가드 축약 없이 해당 행렬을 보존한다.

기본 제어는 변 분할32·실제 fine 접지모드256·보간차수24다. 분할은 짝수10부터
허용하지만 물리 패널512개 한도 때문에 사각형 Trace 세 개에서는 최대48이다.
32→48 비교는 한도를 늘리지 않고 전류 밀도를 세분한다. 패널마다 정적 공간 모드
두 개를 사용한다. 짝수 접지모드64..4096을 유지한다. 전류 패널·체적 유전체 메시·
유한 외곽 비교는 서로 다른 검사이며 이 어댑터가 자동 선택하지 않는다.

전체/면별 금속에는 기존 `SurfaceMetal`·적층 금속·`TraceFaceMetals`·
`ReferenceSurfaceMetals`를 사용한다. 재료·표피깊이·잔존 코어·코팅·거칠기 입력을
전계 계산 전에 검사한다. 전류 추출은 균일 자기 외부 영역으로 유전체 메타데이터가
진공 C0·전류 인자에 들어가지 않는다. 표면 임피던스 변경은 각 물리 면에 따로
적용한다. 유한 금속 확산·일반 미세 거칠기·실측 동박 피팅 기능은 아니다.

별도 비공개 요청 캐시 이름으로 기존 동기 범위 안에서 정확히 같은 전류를
재사용할 수 있다. 기하·라벨·제어·솔버 객체가 같아야 하며 실패는 캐시하지 않는다.
입력 검사는 생략하지 않고 범위 밖으로 캐시를 남기지 않는다. 전류 재사용과 별개로
면별 금속 법칙은 매번 평가한다.

검증에는 비대칭 사다리꼴 세 개,1/3/10GHz 독립 표면 임피던스식, 양의 소모 전력,
상반·수동6포트 망, 특정 면 법칙 변경, 불변 물리 변환, 전류 보존과 분모 바닥값 없는
32/48 세분을 사용한다. 공유 전계의 독립 기준·수치·외곽 검증은 별도 근거다.
정확히 고정한 공유 wheel에 명시 기능이 없으면 대체하지 않고 거부한다.

이 함수 계층은 저장 선로·공차·목표 스키마나 UI를 추가하지 않는다. 고정 접지
Trace·절대 정확도·실측·다른 플랫폼 수락도 뜻하지 않는다. 세 신호 목표 설계에는
별도의 물리량 계약이 필요하다.

[한두 활성 도체의 선형 전류](two_ground_linear_corner_conductor.md) ·
[English](../../../../../packages/sipi/two_ground_harmonic_three_active_corner_conductor.md)

별도 [세 활성 도체 저장 선로](two_ground_harmonic_three_active_corner_face_panel_line.md)는 같은 유전체 전계와6포트 망을 실행 근거와 연결한다.

별도 [두 활성 도체·고정 전위 가드 어댑터](two_ground_harmonic_guard_corner_conductor.md)는 고유 입력 범위·물리 패널 한도·방법 식별을 유지한다.
