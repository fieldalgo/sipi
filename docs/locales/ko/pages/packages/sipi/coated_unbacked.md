# 후면 접지면 없는 평탄 코팅 coplanar 단면

`coated_unbacked_coplanar`와 `coupled_coated_unbacked_coplanar`는 유한 coplanar
접지 두 개 사이의 단일/차동 신호선을 전체 폭의 평탄 코팅에 넣습니다. 유한 기판
아래에는 공기가 있습니다. 모든 외곽은 개방(절연)이며 두 접지 도체만 전기적
기준을 정의합니다. 기존 기하·메시·정전계 솔버 계약을 재사용합니다.

```python
from sipi import coupled_coated_unbacked_coplanar, CrossSectionDocument
section = coupled_coated_unbacked_coplanar(
    width=.5e-3, gap=.3e-3, ground_gap=.2e-3, ground_width=1e-3,
    substrate_height=.5e-3, eps_r=4, tan_delta=.01,
    coating_height=.1e-3, coating_eps_r=3.5, coating_tan_delta=.02,
    thickness=35e-6, top_width=.4e-3,
    lower_air_height=6e-3, air_height=6e-3, box_width=12e-3,
)
saved = CrossSectionDocument(section).dumps()
restored = CrossSectionDocument.loads(saved)
```

길이 단위는 m입니다. 단일 선로의 gap은 신호-접지 간격, 차동선의 gap은 신호 간
간격이며 ground_gap은 바깥쪽 접지까지의 간격입니다. 신호선 밑변을 기준으로
측정합니다. 중앙 접지는 없고 접지는 신호선과 같은 두께의 직사각형입니다.
신호선만 사다리꼴로 만들 수 있습니다. ground_width는 실제 유한 접지 폭이며
무한 접지를 근사하는 외곽 치수가 아닙니다.

층 순서는 lower_air·substrate·coating·air입니다. coating_height는 기판 표면부터
구리 높이를 포함하며 thickness보다 커야 합니다. 위쪽 air_height는 **코팅 위**에서
시작하므로 구리 두께보다 작을 수 있습니다. 기본값은 기판 높이 10배와 구리
두께의 합, 아래 공기 기본값은 기판 높이 10배입니다. 두 공기 높이와 상자 폭의
외곽 수렴을 확인해야 합니다. 기판과 코팅은 상자 전체 폭을 차지합니다. 측면
기판 끝·conformal/meniscus 마스크·3차원 귀환 전류 전이는 모델링하지 않습니다.

두 이름 모두 ImpedanceStudyDocument와 ImpedanceDesignDocument에 연결됩니다.
단일선은 z0, 차동쌍은 z_diff입니다. 네 종류 샘플러는 실패 행을 보존합니다.
고정 피치는 신호 중심을 유지하고 gap=pitch−width를 유도하며 접지는 각 행의
ground_gap을 유지하도록 움직입니다. 잘못된 유계 모서리는 거부하고, 잘못된
정규분포 샘플은 실패로 남깁니다. 기존 JSON 스키마 의미는 유지하며 이전 판독기는
새 이름을 거부합니다. 개발판은 정확한 커밋과 wheel hash도 기록하세요.

## 독립 검증과 범위

두께 0의 진공 도체는 [무후면접지 단면](unbacked_coplanar.md)의 독립적인 중성
자유공간 로그 전하 패널 기준을 사용합니다. 유한 접지 기준을 무한 접지 식으로
대체하지 않습니다. 패널 80→160 모드 변화는 0.3% 이하, 세밀 FEM 오차는 2% 이하이고
거친 메시보다 작아야 합니다. 상자 폭과 양쪽 공기 높이를 두 배로 늘릴 때 모드
변화는 1% 이하입니다.

유한 사다리꼴 구리·기판 eps4·코팅 eps3.5는 같은 메시의 scikit-fem 12.0.2 복소
P1 에너지와 C 상대 차이 1e-9 이하로 비교합니다. 별도 모드 메시 변화는 0.5%,
외곽 변화는 1% 이하입니다. 코팅 eps1·손실0은 코팅 높이만큼 위 공기를 늘린
기존 무코팅 단면과 0.5% 안에서 일치해야 하며 양의 코팅 유전율은 C를 증가시킵니다.
실제 금속 면적을 뺀 재료 면적, 개방 바닥·층 위치, JSON 재현, 얇은 위 공기,
네 샘플러·고정 피치·잘못된 행을 검사합니다. 저장형 폭 목표는 독립 진공 기준을
사용하여 폭 4% 이내, 요청/세밀 메시 잔차 각각 1Ω 이하를 요구합니다.

같은 메시의 일치는 메시 수렴과 다릅니다. 이 단면별 검증은 실측 기판·방사·3차원
비아/스텁·플랫폼 정확도를 보장하지 않습니다. 기존 재료·준TEM 유효 범위를 따릅니다.

[후면 접지 코팅](coated_coplanar.md) · [공차](study.md) · [역산](design.md) ·
[English](../../../../../packages/sipi/coated_unbacked.md)
