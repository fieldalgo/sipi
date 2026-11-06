# 차동 grounded coplanar 단면

[English](../../../../../packages/sipi/coupled_coplanar.md) | **한국어**

`coupled_grounded_coplanar`는 동일 폭 신호선 2개, 양옆 유한 폭 접지 2개와
아래 접지면을 가진 `CrossSection`을 만듭니다. 신호선 사이에는 접지가 없습니다.
기존 준정적 FEM을 사용하며 새 솔버나 고주파 full-wave 모델을 추가하지 않습니다.

```python
from sipi import CrossSectionDocument, coupled_grounded_coplanar

section = coupled_grounded_coplanar(
    width=.5e-3, gap=.3e-3, ground_gap=.2e-3, ground_width=1e-3,
    substrate_height=.5e-3, eps_r=4, thickness=.035e-3,
    air_height=6e-3, box_width=12e-3)
doc = CrossSectionDocument(section,
    mesh=dict(edge_size=2e-6, far_size=.125e-3, grade=.15))
restored = CrossSectionDocument.loads(doc.dumps())
line = restored.analyze()
print(line.even_odd()['z_diff'])
```

길이는 m입니다. `gap`은 두 신호선의 바닥 가장자리 사이 간격,
`ground_gap`은 각 신호선의 바깥 바닥 가장자리에서 인접 접지까지 간격입니다.
`ground_width`는 각 외측 접지의 실제 폭입니다. 신호 중심은
`±(width+gap)/2`, 접지 중심은 `±(width+gap/2+ground_gap+ground_width/2)`입니다.
신호 순서는 `positive`, `negative`, 접지는 `ground_left`, `ground_right`입니다.
신호 2개만 포트를 구성하고 모든 기준 도체는 0 V로 놓습니다.

신호·접지는 `thickness`(기본 0)를 공유합니다. `top_width`는 신호만 사다리꼴로
만들며 접지는 직사각형입니다. 간격은 바닥 기준이므로 위로 넓어지면 실제 이격은
줄어듭니다. 도체 접촉·중첩·영역 밖 형상은 메시 전에 거부합니다.
`tan_delta`는 기판에 적용하고 위층은 공기입니다. 기존 두께·손실·문서 계약을 유지합니다.

기본 공기 높이는 `10*h+t`, 영역 폭은
`max(20*h,4*w,2*w+gap+2*ground_gap+2*ground_width+4*h)`입니다.
위·옆 경계는 전속의 법선 성분이 0인 유한 영역 근사입니다. 메시·폭·공기 높이를
각각 확인해야 합니다. 유한 `ground_width`는 물리적 형상이므로 더 큰 접지 또는
무한 접지 근사를 조사할 때만 늘립니다.

## 저장·공차·역산

기존 단면 JSON이 도체 4개와 접지 플래그를 저장하므로 새 단면 스키마가 필요하지
않습니다. `sipi.impedance-study/1`은 `coupled_grounded_coplanar`와
`quantity='z_diff'`를 받습니다. sweep·corners·균등·상관 정규분포와 실패 행 보존은
기존 계약을 따릅니다. 이전 판독기는 새 이름을 거부하므로 엔진 버전을 기록하세요.

고정 피치 `fixed_pitch_m=width+gap`은 **신호선 중심**을 고정합니다. 외측 접지는
각 행의 `ground_gap`을 유지하도록 신호의 바깥 가장자리와 함께 이동하므로 고정된
접지 좌표를 뜻하지 않습니다. 제조 레이아웃에서 접지 위치를 고정하는 등 다른
배치 제약은 명시적 `CrossSection`으로 정의하세요.

`seek_impedance`에 단면 factory와 `quantity='z_diff'`를 주면 기존 유계 탐색과
별도 세분 메시 확인을 사용합니다. 목표를 bracket하고 두 메시 모두 목표 허용오차를
충족해야 합니다. 임의 형상의 단조성이나 제조 수율을 보장하지 않습니다.
[역산](design.md)·[공차](study.md)를 참조하세요.

## 독립 기준과 수락 기준

`tests/sipi/test_coupled_coplanar.py`의 시험 전용 적분 계산은 SIPI 형상·메시·솔버를
사용하지 않습니다. 진공에서 무한 접지면 위 높이 h에 놓인 두께 0 도체에 대해
영상 전하 Green kernel은 다음과 같습니다.

`G(x,x') = log(sqrt((x-x')²+(2h)²)/abs(x-x')) / (2*pi*epsilon_0)`.

패널별 일정 전하·중점 collocation·해석적 패널 적분을 사용하고 cosine 간격으로
모서리 특이점 근처를 세분합니다. 전위로부터 전하와 정전용량 행렬을 계산하며
외측 도체 전위는 0입니다. 균일 매질 TEM에서는
`Z_even/odd=1/(c*(C11±C12))`입니다. 이 기준은 아래 접지면 위 무한 공간을
가정하므로 FEM의 유한 위·옆 경계와 독립적입니다. 로그 특이점을 포함한 적분을
별도 적응 구적법으로 대조하고, 상반성·양의 정전용량·치수 배율 불변성도 확인합니다.

결과를 보기 전에 정한 기준:

- 도체당 패널 80→160의 모드 임피던스 변화 0.3% 미만.
- FEM coarse→fine 각 모드 오차 감소, fine 오차 2% 미만.
- 영역 폭·공기 높이 두 배 시 모드 임피던스 변화 1% 미만.
- 독립 적분에서 얻은 차동 목표로 폭 역산: 두 메시의 잔차 모두 1 Ω 이하,
  기준 폭 대비 4% 이내.

기준은 폭 .5 mm, 신호 간격 .3 mm, 접지 간격 .2 mm, 접지 폭 1 mm,
기판 높이 .5 mm, 상대유전율 1, 두께 0입니다. FEM 영역 폭/공기 높이는
12/6 mm에서 24/12 mm로 확장합니다. coarse `(edge_size,far_size,grade)`는
`(8 um,.25 mm,.3)`, fine은 `(2 um,.125 mm,.15)`입니다.
Linux CPython 3.12.14에서 독립 even/odd는 131.91940/86.22839 Ω,
fine FEM은 132.02692/85.91806 Ω(오차 0.0815%/0.3599%), 확장 영역은
131.68938/85.91612 Ω(변화 0.256%/0.0023%)였습니다.
이상화한 해당 조건의 근거이며 실측 기판·유한 두께·임의 유전체의 오차 보증이
아닙니다. 유한 구리와 유전체 조건은 형상·입력·API 회귀를 확인하며 정확도는
별도 메시·재료 검증이 필요합니다.

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python -m pytest -q -s tests/sipi/test_coupled_coplanar.py
```
