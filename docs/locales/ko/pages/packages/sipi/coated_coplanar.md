# 평탄 코팅 coplanar 단면

`coated_grounded_coplanar`와 `coupled_coated_grounded_coplanar`는 두 유한 접지
도체 사이에 표면 신호선 하나 또는 두 개를 둡니다. 모든 도체를 같은 평탄한
전폭 유전체층으로 덮습니다. 지정한 단면이며 conformal mask·meniscus·제조
과정의 형상을 예측하지 않습니다.

```python
from sipi import coupled_coated_grounded_coplanar, CrossSectionDocument
section = coupled_coated_grounded_coplanar(
    width=.5e-3, gap=.3e-3, ground_gap=.2e-3, ground_width=1e-3,
    substrate_height=.5e-3, eps_r=4, thickness=.035e-3, top_width=.4e-3,
    coating_height=.1e-3, coating_eps_r=3.5, coating_tan_delta=.02,
    air_height=6e-3, box_width=12e-3,
)
saved = CrossSectionDocument(section).dumps()
restored = CrossSectionDocument.loads(saved)
```

길이 단위는 m입니다. 단일선의 `gap`은 신호선 바닥 가장자리와 접지 사이,
차동쌍의 `gap`은 신호선 바닥 가장자리 사이 간격입니다. 차동쌍의
`ground_gap`은 각 바깥 신호선 가장자리와 접지 사이입니다. 중앙 접지는 없으며
`ground_width`는 실제 유한 접지 폭이고 무한 접지 설정이 아닙니다. 신호선만
테이퍼를 지원하며 접지는 신호선과 두께·바닥 높이가 같은 직사각형입니다.
`coating_height`는 기판에서 시작해 **구리를 포함**하므로 `thickness`보다 커야
합니다. `air_height`는 코팅 위에서 시작합니다. 바닥은 접지, 위·옆은 기존
자연 경계 근사이며 메시 세분과 별개로 외곽 수렴을 확인해야 합니다.

층 이름은 `substrate`, `coating`, `air`입니다. 기판과 코팅의 유전율·손실탄젠트는
독립적입니다. 기존 단면 JSON이 형상을 보존합니다. 두 템플릿 모두
`ImpedanceStudyDocument`와 `ImpedanceDesignDocument`에서 사용할 수 있으며
단일선은 `z0`, 차동쌍은 `z_diff`를 사용합니다. 네 샘플링 방식의 기존 의미를
유지합니다. 차동쌍 고정 피치는 신호선 중심을 고정하고 gap=pitch−width를
유도하며 각 행의 `ground_gap`을 유지하도록 접지를 움직입니다. 유계 영역의
잘못된 모서리는 거부하고 잘못된 정규 표본은 재추출 없이 실패 행으로 남깁니다.
이전 판독기는 새 이름을 거부하므로 입력과 함께 SIPI 버전을 기록하세요.

`tests/sipi/test_coated_coplanar.py`는 다음 검증을 구분합니다.

- 두께 0·진공·유한 접지: 독립 image-charge 패널 적분의 80→160 패널 변화
  <=0.3%, 세분 메시 모드 임피던스 오차 <=2% 및 세분 시 감소, 외곽 2배 변화 <=1%.
- 유한 테이퍼 구리·기판 eps=4·코팅 eps=3.5: 같은 메시에서 scikit-fem 12.0.2의
  복소 P1 에너지 행렬과 상대 <=1e-9. 조립 검증이며 별도로 메시 변화 <=0.5%,
  외곽 변화 <=1%, eps=1 코팅의 비코팅 환원 <=0.5%를 요구합니다.
- 금속을 뺀 정확 코팅 면적, 엄격 단면 JSON 재현, 네 샘플러·고정 신호 피치·
  잘못된 표본. 저장형 선폭 역산은 독립 진공 목표에 대해 폭 오차 <=4%,
  요청·세분 메시 잔차 모두 <=1Ω를 요구합니다.

검사한 형상에 대한 수치 기준이며 실측 기판 정확도나 보편적 오차 보장은 아닙니다.
[제조 단면](manufacturing_sections.md) · [공차](study.md) · [역산](design.md)
