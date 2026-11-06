# Coplanar 도체의 법선 두께 코팅

유한 옆 접지에도 [법선 두께의 miter 막](conformal_coating.md)을 적용하는
4종 템플릿입니다. 모든 신호·접지도체를 코팅하며 신호만 경사 단면을 허용합니다.
신호쌍 가운데 접지는 없습니다.

| 템플릿 | 신호 수 | 후면 접지면 |
|---|---:|---|
| `conformal_coated_grounded_coplanar` | 1 | 있음 |
| `coupled_conformal_coated_grounded_coplanar` | 2 | 있음 |
| `conformal_coated_unbacked_coplanar` | 1 | 없음 |
| `coupled_conformal_coated_unbacked_coplanar` | 2 | 없음 |

```python
from sipi import coupled_conformal_coated_unbacked_coplanar, CrossSectionDocument

section = coupled_conformal_coated_unbacked_coplanar(
    width=.5e-3, gap=.3e-3, ground_gap=.2e-3, ground_width=1e-3,
    substrate_height=.5e-3, eps_r=4, tan_delta=.01,
    thickness=35e-6, top_width=.4e-3,
    coating_thickness=20e-6, coating_eps_r=3.5, coating_tan_delta=.02,
    air_height=6e-3, lower_air_height=6e-3, box_width=12e-3)
document = CrossSectionDocument(section,
    mesh=dict(edge_size=4e-6, far_size=.25e-3, grade=.2))
restored = CrossSectionDocument.loads(document.dumps())
line = restored.analyze()
assert line.C.shape == (2, 2)
```

길이 단위는 m입니다. 단일선 `gap`은 신호–접지 바닥 모서리 사이 간격입니다.
쌍의 `gap`은 신호끼리, `ground_gap`은 외곽 신호–접지 사이 간격입니다.
`ground_width`는 양쪽 접지의 실제 유한폭이며 무한 접지로 바꾸지 않습니다.
신호와 직사각형 접지는 같은 `thickness`를 쓰며 신호 `top_width`는 `width`
이하여야 합니다. 기존 bare coplanar의 치수 의미를 유지합니다.

`coating_thickness`는 법선 막 두께이며 평탄 채움 높이가 아닙니다. 직선 이동면이
miter 모서리에서 만나고 접촉한 막은 `coating` 국소 영역으로 합칩니다. 기판
윗면과 모든 도체 면을 덮되 기판 아랫면은 코팅하지 않습니다. 메시에서는 금속이
우선합니다. 위로 넓어지는 도체·둥근 모서리·meniscus·밀폐 공기·증착 공정은
모델링하지 않습니다. 막이 box 측면을 넘으면 자르지 않고 거부합니다.

위쪽 `air_height`는 최고 막 표면 위에서 시작하며 기본값은 10h+t(h는 기판,
t는 구리 두께)입니다. 후면 접지면이 없으면 양의 `lower_air_height`(기본 10h)가
전체 기판·모든 도체·국소 막을 함께 이동합니다. 외곽 경계는 모두 open이고
옆 접지도체 두 개만 기준입니다. grounded 변형에는 아래 접지면을 유지합니다.
공차·수렴 연구에는 외부 크기를 명시하는 편이 좋습니다.

lower_air 이동 뒤에도 [막 해상도 조건](conformal_coating.md)을 적용합니다.
미해상 양의 틈·얇은 금속/막·공기층은 메시 전에 거부합니다. 이미 합쳐진 경계의
일직선 꼭짓점만 없애며 형상을 임의로 붙이지 않습니다.

## 저장 입력·공차·역산

[단면 v3](polygon_sections.md)의 substrate·air 층(후면 없는 경우 lower_air
추가)과 coating 국소 영역을 씁니다. 기존 [선로 입력](line_model.md)에서
coating을 스칼라 또는 [주축 재료](principal_dielectrics.md)로 지정할 수 있습니다.
재료까지 보존하려면 전체 입력을 저장하세요.

4종 모두 [저장 공차](study.md)와 [폭 역산](design.md)을 지원합니다. 쌍은
`z_diff`, 나머지는 `z0`입니다. 고정 피치는 신호 중심만 고정하며 옆 접지는
ground_gap을 유지하도록 외곽 신호 모서리와 함께 움직입니다. 폭·막 두께 상관
샘플링, 실패 행 보존, [고정 주파수 재료 계약](material_impedance.md)은 그대로입니다.
기존 스키마 필드를 바꾸지 않고 이름을 추가하므로 이전 리더는 새 이름을
거부합니다. 국소 막의 이동 보존을 더해도 기존 bare/평탄 unbacked JSON은 불변입니다.

## 검증과 한계

Linux/Python 3.12.14·NumPy 2.5.4·SciPy 1.18.1·Shapely 2.2.0 및 시험 전용
scikit-fem 12.0.2에서 신규 72개 시험이 통과했습니다. 독립 복소 C의 최대 차는
6e-15 미만, 세분 진공 패널 기준 오차는 아래 표 순서로 최대
0.127%/0.158%/0.184%/0.168%입니다.
별도 해상도 시험 41개는 법선 막 6종에서 미해상 양의 틈·치수의 메시 전 거부,
정확 접촉/겹침 정리의 다각형 보존(대칭차 면적 0), 구리 두께 0과 해상 가능한
양의 공기 틈 보존을 확인합니다.

얇은 진공 단면은 grounded에서 독립 영상전하 패널, unbacked에서 중성 로그
Green 함수 패널과 비교합니다. 패널 세분 변화는 0.3% 미만, 세분 FEM 오차는
개선되면서 2% 이하여야 합니다. 시험 전용 scikit-fem의 독립 복소 P1 조립은
C 상대차 1e-9 이내를 요구합니다. 막 면적·측면 법선 거리·접지 덮임·반사
항등식을 별도로 확인합니다.

예제 치수의 사전등록 메시 연구는 edge 4→1 µm, far .25→.125 mm,
grade .2→.1입니다. 외곽 연구는 세분 메시에서 box 폭과 모든 외부 air 높이를
별도로 2배 늘립니다. 복소 C 원소의 최대 상대 변화는 다음과 같습니다.

| 단면 | 메시 | 외부 영역 |
|---|---:|---:|
| 후면 접지 단일선 | 0.3433% | 0.0269% |
| 후면 접지 쌍 | 0.7368% | 0.1746% |
| 후면 없는 단일선 | 0.4016% | 0.0038% |
| 후면 없는 쌍 | 0.4704% | 0.0117% |

각각 1% 관문 이내입니다. 두께 0의 평탄 막 및 공기 재료 환원은 별도 0.5%
관문을 씁니다. 저장 목표 60 Ω 단일선/100 Ω 쌍은 requested·refined 메시 모두
잔차 1 Ω 이내를 요구합니다. JSON 재현, 스칼라/주축 재료 동등성, 상관 기하
공차와 무효 입력을 따로 검사합니다. 이는 수치 수락 기준이며 제조·실측 정확도
보증이 아닙니다. 새 기하의 수렴은 별도로 확인해야 합니다. 공유 솔버·런타임
의존성·번들 바이너리·지원 플랫폼 주장을 추가하지 않으며 기존 고지를 따릅니다.

나머지 치수는 유지하고 신호를 직사각형으로 둔 저장 폭 목표 결과입니다.

| 단면·목표 | 폭, mm | Requested 잔차, Ω | Refined 잔차, Ω |
|---|---:|---:|---:|
| 후면 접지 단일선, 60 Ω | .3875 | −.2555 | −.1011 |
| 후면 접지 쌍, 100 Ω | .434375 | −.2660 | −.0134 |
| 후면 없는 단일선, 60 Ω | .7000 | +.6084 | +.7682 |
| 후면 없는 쌍, 100 Ω | .54375 | −.1219 | +.1436 |

이는 유계 수치 목표의 결과이며 제조 공차 보증이 아닙니다.

[English](../../../../../packages/sipi/conformal_coplanar.md)
