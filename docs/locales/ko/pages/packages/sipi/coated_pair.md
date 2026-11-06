# 평탄 코팅 안의 edge-coupled 차동선

`coupled_coated_microstrip`는 기판 표면의 동일 폭 `positive`/`negative` 신호와
전체 폭의 평탄 코팅, 위쪽 공기를 기존 `CrossSection`으로 만듭니다. 지정한
평탄 단면이며 conformal mask·meniscus나 실제 제조 형상 예측은 아닙니다.

```python
from sipi import coupled_coated_microstrip, CrossSectionDocument
section = coupled_coated_microstrip(
    width=.5e-3, gap=.3e-3, substrate_height=.5e-3, eps_r=4,
    thickness=.035e-3, top_width=.4e-3, coating_height=.1e-3,
    coating_eps_r=3.5, tan_delta=.01, coating_tan_delta=.02,
    air_height=6e-3, box_width=12e-3,
)
document = CrossSectionDocument(section)
restored = CrossSectionDocument.loads(document.dumps())
```

치수 단위는 m입니다. `gap`은 바닥 모서리 간격이고 중심은 ±(width+gap)/2입니다.
`coating_height`는 기판 표면부터 시작해 **금속을 포함**하므로 `thickness`보다
커야 합니다. `air_height`는 코팅 위에서 시작하며 `top_width`는 신호 taper만
바꿉니다. 아래는 접지, 위·옆은 기존 자연 경계 근사입니다. 메시 세분과 별도로
외곽 영역의 수렴을 확인해야 합니다.

층 이름 `substrate`, `coating`, `air`는 기존 재료 문서에 사용할 수 있습니다.
기판/코팅 유전율과 손실은 독립입니다. 단면 JSON으로 형상을 저장합니다.
`ImpedanceStudyDocument`, `ImpedanceDesignDocument`는 새 이름과 `z_diff`를
받습니다. 고정 pitch는 gap=pitch−width를 유도해 중심을 유지합니다. 금속 두께만
바꾸면 고정 코팅 상면까지 여유가 달라집니다. 잘못된 bounded corner는 거부하고
normal의 무효 표본은 실패 행으로 남깁니다. 이전 판독기는 새 이름을 거부하므로
입력과 함께 SIPI 버전을 기록하세요.

다음은 특정 형상의 검증 기준이며 모든 단면의 정확도 보증은 아닙니다.

- 두께 0 진공: 독립 두 strip image-charge panel 적분. 80→160 panel 변화
  0.3% 이하, fine even/odd Z 오차 2% 이하 및 메시 오차 감소, 외곽 두 배 변화 1% 이하.
- 유한 taper 금속, 기판 eps=4/코팅 eps=3.5: 같은 메시의 scikit-fem 12.0.2
  복소 P1 행렬과 상대 차이 1e-9 이하. 조립 검증이며 메시 정확도 근거는 아닙니다.
  별도로 모드 메시 변화 0.5%, 외곽 변화 1%, eps=1 코팅의 일반선 환원 차이
  0.5% 이하가 필요합니다.
- 정확한 면적/경계, JSON 재현, 네 가지 샘플링·고정 pitch·형상 오류를 확인합니다.
  독립 진공 적분을 목표로 저장한 폭 역산은 폭 4% 이내, 요청/세분 메시 잔차
  모두 1Ω 이하입니다. 실제 제조 기판의 측정 검증은 아닙니다.

[제조 단면](manufacturing_sections.md) · [공차](study.md) · [역산](design.md)
