# 표면 도체를 따라가는 법선 두께 코팅

`conformal_coated_microstrip`과 `coupled_conformal_coated_microstrip`은 접지된
기판 위 단일선·차동쌍에 유전체 막을 더합니다. 각 직선 면의 법선 방향 두께가
일정하며, 이동한 면은 뾰족한 교차 모서리(miter)에서 만납니다. 실측 증착 형상이
아닌 이상화 단면입니다.

```python
from sipi import coupled_conformal_coated_microstrip, CrossSectionDocument

section = coupled_conformal_coated_microstrip(
    width=.5e-3, gap=.3e-3, substrate_height=.5e-3, eps_r=4,
    thickness=35e-6, top_width=.4e-3, tan_delta=.01,
    coating_thickness=20e-6, coating_eps_r=3.5, coating_tan_delta=.02,
    air_height=4e-3, box_width=8e-3)
document = CrossSectionDocument(section,
    mesh=dict(edge_size=4e-6, far_size=.25e-3, grade=.2))
restored = CrossSectionDocument.loads(document.dumps())
line = restored.analyze()
assert line.C.shape == (2, 2)
```

길이 단위는 m입니다. 양의 `coating_thickness=d`는 기판 평면·도체 윗면·경사
측면의 법선 막 두께입니다. 구리 높이를 포함하는 기존 평탄 `coating_height`와
다릅니다. 도체 두께는 0 이상, `top_width`는 `width` 이하이며 위로 넓어지는
형상은 거부합니다. 쌍의 `gap`은 바닥 모서리 사이 간격입니다. 아래 평면은 접지,
상단·측면은 외부 영역을 자른 열린 경계입니다.

기판 높이가 h, 도체 두께가 t이면 평면 막은 h+d, 최고 막 표면은 h+t+d입니다.
`air_height`는 최고 막 위 여유 높이이며 기본값은 10h+t입니다. 기본 box 폭은
해당 bare 템플릿과 같습니다. 수렴 확인에는 외부 크기를 명시하는 편이 좋습니다.
막이 box 측면을 넘으면 자르지 않고 거부하며 부동소수점으로 분리해 표현하지
못하는 막·공기 높이도 거부합니다.

t>0에서 측면 기울기 s=(width-top_width)/(2t), δ=d/(sqrt(1+s²)+s)라 두면
도체 사다리꼴을 위로 d 이동하고 양쪽을 δ 확장한 영역이 위쪽 막 외곽입니다.
이를 평면 막과 합쳐 `coating`이라는 단일 단순 영역으로 저장합니다. 쌍의 막이
겹치면 같은 유전체로 합치며 밀폐 공기주머니를 만들지 않습니다. 메시에서는
금속이 유전체보다 우선합니다. 위쪽 막이 겹치지 않을 때 실제 막 면적은
Wd+Σ2δt(W는 box 폭), t=0이면 기존 평탄 막으로 환원됩니다.

## 저장·재료·공차·역산

substrate·air는 층, coating은 국소 유전체 영역입니다.
[단면 JSON v3](polygon_sections.md)가 다각형을 보존하며 기존 선로·체적 선로
문서에서도 사용합니다. `materials={'coating': model}`로 스칼라 또는 주축 재료를
지정할 수 있습니다. 재료까지 재현하려면 전체 선로 입력을 저장하세요.

두 이름을 [저장형 공차](study.md)와 [목표 역산](design.md)에서 사용할 수 있습니다.
`coating_thickness`를 다른 기하 치수와 함께 샘플링하며 상관 정규분포의 실패
행도 보존합니다. 쌍은 공차의 신호 고정 피치와 `z_diff`, 단일선은 `z0`를 씁니다.
[고정 주파수 재료 공차·역산](material_impedance.md)의 실수 준정적 임피던스
정의와 대칭 제약은 그대로입니다. 복소 특성 행렬 목표가 아닙니다. 기존 JSON
필드·템플릿 의미는 바뀌지 않으며 새 이름을 모르는 이전 리더는 거부합니다.

## 검증과 한계

신규 41개 시험을 Linux/Python 3.12.14·NumPy 2.5.4·SciPy 1.18.1·Shapely 2.2.0,
시험 전용 scikit-fem 12.0.2로 확인했습니다. 수락 기준은 구현 전에 정했습니다.
독립 막 면적·법선 거리·반사·합쳐지는 막, 두께 0/공기 재료 환원(0.5%), JSON,
상관 기하 샘플링, 재료 지정, 체적 추출과 무효 기하를 확인합니다. 같은 메시의
독립 복소 P1 조립 대비 C 상대차는 1e-9 기준 이내(관측 최대 5e-15 미만)입니다.

예제 단일선/쌍의 edge 4→1 µm, far .25→.125 mm, grade .2→.1 세분에서
복소 C 변화는 각각 0.256%/0.689%, 세분 메시의 air·box를 별도로 2배 늘리면
0.196%/0.647%입니다. 각각 사전 1% 관문을 통과했으며 실측 정확도 보증이 아닙니다.

직사각형 도체의 저장 폭 목표 60 Ω 단일선/100 Ω 차동은 폭 .69375/.553125 mm,
requested/refined 잔차 (.2424,.3332) Ω 및 (−.3764,−.1519) Ω로 각각 1 Ω 이내입니다.
유전율 증가의 C 단조성과 양의 손실도 확인했습니다.

둥근 모서리·meniscus·위로 넓어지는 도체·밀폐 공기·공정별 막 두께는 미지원입니다.
새 기하는 얇은 막·금속 모서리·외부 영역을 별도로 세분하세요. 새 런타임 의존성이나
바이너리를 번들하지 않으며 기존 Shapely·독립 시험 도구의 고지를 따릅니다.
Windows EXE 동작이나 3D 정확도를 검증한 결과가 아닙니다.

[English](../../../../../packages/sipi/conformal_coating.md)
