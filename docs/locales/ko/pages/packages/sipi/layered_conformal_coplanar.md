# 두 기판 위의 법선 코팅 coplanar 단면

[English](../../../../../packages/sipi/layered_conformal_coplanar.md) | **한국어**

`layered_conformal_coated_grounded_coplanar`,
`layered_conformal_coated_unbacked_coplanar` 및 `coupled_`·`asymmetric_coupled_`
변형은 두 기판 재료·유한 옆 접지선·직선 법선 두께 코팅을 결합합니다. 두 기판
높이는 구리를 제외합니다. `coating_thickness`는 기판과 구리 표면에 수직이며
옮긴 변은 모서리에서 직선으로 만납니다. 공기 높이는 가장 높은 코팅 위부터입니다.
모든 신호·접지선 외피를 다각형 코팅에 보존합니다. 돌출된 윗면·암묵적 잘림·
미해상 코팅·갇힌 공기 구멍은 거부하며 둥근 모서리·메니스커스·실측 증착을 뜻하지 않습니다.

Grounded는 하단 접지면과 열린 상단·옆면을 유지합니다. Unbacked는 모든 외곽이
열려 있으며 명시적인 아래 공기가 두 기판층·모든 구리·코팅 다각형을 함께 옮깁니다.
아래 공기의 기본값은 두 기판 높이 합의 10배입니다. 이 경우 두 유한 옆 접지선만
기준 전위를 정합니다. 공통 전위는 3D 접속의 모델링을 의미하지 않습니다.

단일선의 `gap`은 신호·접지 바닥 변 사이 간격입니다. 쌍의 `gap`은 신호끼리,
`ground_gap`은 바깥 신호와 접지 사이 간격입니다. 비대칭 신호는 바닥·위쪽 폭과
두께를 독립 지정하며 직사각형 접지선의 폭·두께도 명시합니다. 접지 폭·상자 폭·
상하 공기는 서로 다른 매개변수로 각각 민감도 검사가 필요합니다.

```python
from sipi import layered_conformal_coated_unbacked_coplanar, CrossSectionDocument
section = layered_conformal_coated_unbacked_coplanar(
    width=0.5e-3, gap=0.2e-3, ground_width=1e-3,
    thickness=35e-6, top_width=0.4e-3,
    lower_height=0.3e-3, upper_height=0.7e-3,
    lower_eps_r=3., upper_eps_r=5.,
    lower_tan_delta=0.01, upper_tan_delta=0.03,
    coating_thickness=20e-6, coating_eps_r=3.3, coating_tan_delta=0.02,
    air_height=10e-3, lower_air_height=10e-3, box_width=20e-3)
text = CrossSectionDocument(section).dumps()
```

Python 직접 호출·기하 JSON·이름 기반 입력·공차·폭 목표는 같은 단면 계약을
사용합니다. 전용 입력 화면은 별도 연결 단계입니다. 단일 `z0`, 대칭쌍 even/odd 진단, 비대칭 `z_diff_forward`의
기존 의미를 유지합니다.

대표 검사는 예제 기판·코팅을 사용합니다. 대칭 신호는 바닥·위쪽 폭 0.5/0.4 mm,
두께 35 µm이며 비대칭은 바닥 폭 0.4/0.7 mm·위쪽 폭 0.32/0.55 mm·두께
25/45 µm입니다. 쌍 간격은 0.3 mm·접지 간격은 0.2 mm·접지 폭은 1 mm·
접지 두께는 35 µm입니다. 독립 직선 법선 오프셋 재료 마스크와 scikit-fem P1
복소·진공 조립의 정규화 차이는 1e-10 이하여야 합니다. edge 5 µm·far 0.25 mm·
grade 0.2를 절반으로 세분한 C·해당 임피던스 변화는 1% 이하, 세분 메시에서
상자 폭·위 공기·unbacked 아래 공기를 각각 두 배로 바꾼 변화는 0.5% 이하입니다.
균일 기판·유전율 1 코팅·구리 두께 0의 평면 코팅 극한도 각각 0.5% 이내로
일치해야 합니다. 법선 거리·이동·접지 간격·진공 항등식·양의 에너지·상반성·JSON을
함께 검사하며 임의 보드나 실측 정확도를 인증하지 않습니다.


## 저장 공차와 폭 목표

6종은 단일선 `z0`, 대칭쌍 `z_diff` 또는 명시적 `z_diff_forward`, 비대칭쌍
`z_diff_forward`의 목표 구분을 유지합니다. 고정 피치는 신호 중심 간격을
대칭·비대칭 예제에서 각각 0.8/0.85 mm로 보존하며 옆 접지선은 명시적인
바닥 간격을 유지하도록 바깥 금속 변을 따라갑니다. 다각형 코팅은 유한 접지선
주위까지 법선 두께 20 µm를 유지하고 상하 공기의 의미도 보존합니다. 고정 접지면
간격은 이 표면 단면의 변수가 아닙니다.

코팅 유전율 3.1→3.5의 스윕은 저장·공통 실행과 일치합니다. 독립 PCG64 표본과
음수 코팅의 실패 행도 검사하며 잘못된 행은 메시를 만들거나 재표본화하지 않습니다.
기존 JSON 스키마 버전을 재사용합니다.

하단 접지 예제의 단일·대칭·비대칭 목표는 55/95/95 Ω, unbacked는
60/95/95 Ω입니다. 폭 0.4–0.7 mm 또는 비대칭 왼쪽 폭 0.32–0.8 mm를
사용합니다. 탐색 기준은 0.05 Ω이며 요청·별도 세분 메시의 잔차는 각각 0.5 Ω
이하여야 합니다. 원래 edge 5 µm·far 0.25 mm·grade 0.2를 선택 기하에서
각각 절반으로 줄여 세분합니다. 직접·저장 이력과 세분 결과는 정확히 일치해야
합니다. 이 검사는 명목 기하의 외곽 수렴과 구분하며 임의 입력의 수락을 뜻하지 않습니다.
