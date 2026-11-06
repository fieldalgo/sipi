# 두 유전체를 가진 스트립라인

[English](../../../../../packages/sipi/layered_stripline.md) | **한국어**

`layered_stripline`과 `coupled_layered_stripline`은 두 접지면 사이의 유전체 경계에
단일선 또는 동일 폭 차동쌍을 놓습니다. FEM에서 각 층의 유전율과 손실을 각각
사용하며 템플릿이 재료를 평균하지 않습니다.

```python
from sipi import CrossSectionDocument, layered_stripline

section = layered_stripline(
    width=.5e-3, lower_height=.3e-3, upper_height=.7e-3,
    lower_eps_r=3.5, upper_eps_r=4.2, thickness=.035e-3,
    lower_tan_delta=.01, upper_tan_delta=.015, box_width=12e-3)
doc = CrossSectionDocument(section,
    mesh=dict(edge_size=2e-6, far_size=.125e-3, grade=.15))
restored = CrossSectionDocument.loads(doc.dumps())
print(restored.analyze().z0)
```

길이는 m입니다. 필수 입력은 `width`, `lower_height`, `upper_height`,
`lower_eps_r`, `upper_eps_r`이며 차동쌍은 `gap`도 필요합니다.

| 위치 | y 좌표 |
|---|---|
| 아래 접지 | 0 |
| 유전체 경계·신호 바닥 | `lower_height` |
| 신호 윗면 | `lower_height+thickness` |
| 위 접지 | `lower_height+upper_height` |

**upper_height는 구리 두께를 포함합니다.** 위쪽 유전체는 구리의 옆·위에 있으며
아래쪽 유전체는 구리 바닥에서 끝납니다. 위 접지 이격 `upper_height-thickness`는
양수여야 합니다. 특정 적층 경계를 정의하는 규칙이며 구리 중심을 경계에 놓지
않습니다. 다른 적층은 명시적 `CrossSection` 층·도체·국소 유전체로 정의하세요.

기본 `thickness=0`, `top_width=None`은 이상적인 얇은 직사각형 선로입니다.
두께가 양수이면 `top_width`로 대칭 사다리꼴을 만들 수 있습니다. 차동쌍의 `gap`은
바닥 가장자리 사이이며 중심은 `±(width+gap)/2`입니다. 위로 넓어지면 실제 간격이
줄어듭니다. 도체 접촉·중첩·접지면 접촉은 거부합니다. 신호 이름은 `signal` 또는
`positive`, `negative`; 층 이름은 `lower`, `upper`입니다.
`lower_tan_delta`, `upper_tan_delta`의 기본값은 0입니다. 유전율>=1, 손실>=0이며
입력은 유한 실수이고 bool은 받지 않습니다.

위·아래 접지는 0 V이며 옆 경계는 전속의 법선 성분이 0인 유한 영역 근사입니다.
기본 폭은 단일선 `max(12*(lower_height+upper_height),4*width)`, 차동쌍은 여기에
`4*(2*width+gap)` 이상입니다. 폭 확장과 메시 세분을 따로 확인해야 하며 기본값은
외곽 수렴을 보장하지 않습니다. 공기층은 없습니다.

## JSON·공차·목표 역산

기존 단면 JSON이 두 층의 재료와 도체 좌표를 저장하므로 스키마를 변경하지
않습니다. `sipi.impedance-study/1`에서 `layered_stripline`은 `quantity='z0'`,
`coupled_layered_stripline`은 `quantity='z_diff'`입니다. 네 샘플링 방식 모두 각
재료·높이를 독립적으로 바꿀 수 있습니다. 이전 판독기는 새 이름을 거부하므로
엔진 버전을 기록하세요.

한쪽 높이를 바꾸면 전체 접지면 간격도 바뀝니다. 전체 간격을 고정하려면 다른
높이를 계산하는 명시적 factory가 필요하며 자동 공차 제약이 아닙니다.
차동쌍의 `fixed_pitch_m`은 `gap=pitch-width`로 수평 신호 중심을 고정합니다.
유계 입력은 모든 모서리 형상을 검사하고, 잘못된 비유계 정규 표본은 다시 뽑거나
부분 통계를 내지 않고 실패 행으로 남깁니다.

`seek_impedance`에 폭 등 양의 변수에 대한 factory를 전달하고 차동쌍은 `z_diff`를
선택합니다. 요청 메시와 별도 세분 메시가 모두 목표 허용오차를 충족해야 합니다.
[역산](design.md)·[공차](study.md)를 참조하세요. 제조 수율을 보장하지 않습니다.

## 대칭 경계의 독립 해석 기준

구리 두께가 0이고 **위아래 높이가 같으면** 유전체 경계는 전위의 반사 대칭면입니다.
신호 밖 경계에서 수직 전기장은 0이므로 두 반쪽의 기하 정전용량 기여가 같습니다.
따라서 실수 유전율에 대해 정확히 다음이 성립합니다.

`C=C0*(eps_lower+eps_upper)/2`.

복소 유전율에 같은 논리를 적용하면

`tan_eff=(eps_lower*tan_lower+eps_upper*tan_upper)/(eps_lower+eps_upper)`.

이 특수 조건에서 기존 독립 Cohn 등각사상 단일·차동 스트립라인 식에 평균 유전율을
넣을 수 있습니다. 인덕턴스는 진공 형상을 사용합니다. **높이가 다르거나 유한
구리 두께에서는 이 평균을 적용할 수 없으며** 명시적 재료 분포를 해석합니다.

시험은 폭 .5 mm, 높이 .5/.5 mm, 유전율 2/6, 두께 0, 쌍 간격 .3 mm,
영역 폭 12→24 mm입니다. coarse `(edge_size,far_size,grade)`는
`(8 um,.25 mm,.3)`, fine은 `(.5 um,.0625 mm,.075)`입니다.
측정 전에 정한 기준:

- fine 단일/even/odd 임피던스의 Cohn 대비 오차<=0.5%, coarse 대비 각각 감소.
- 영역 폭 두 배 시 임피던스 변화<=0.2%.
- 유효 유전율·가중 손실(tan값 .01/.02)은 상대오차<=0.3%.
- 50 Ω 단일선 폭 역산은 독립 Cohn 근과 1% 이내, 두 메시 잔차 모두<=0.2 Ω.

Linux CPython 3.12.14 측정 결과:

| 값 | Cohn (Ω) | Fine FEM (Ω) | 상대 오차 |
|---|---:|---:|---:|
| 단일선 Z | 50.216225 | 50.185967 | 0.0603% |
| 차동쌍 even Z | 56.383287 | 56.359933 | 0.0414% |
| 차동쌍 odd Z | 43.135982 | 43.104478 | 0.0730% |

50 Ω 폭 역산은 `.503125 mm`, Cohn 근은 `.503967674 mm`이며 요청/세분 메시
잔차는 `.01927/.03625 Ω`입니다. 명시한 시험 조건과 환경의 측정값입니다.

다른 높이·유한 사다리꼴 구리의 형상, JSON의 C/C0/L/손실 보존, 잘못된 입력,
독립 재료 표본, 고정 피치와 실패 정규 표본 보존도 확인합니다. 이 검사는 입력·연결
동작의 근거이며 대칭 이상 조건의 수치 검증을 임의 적층·유한 구리·실측 기판
전체의 정확도 보증으로 확대하지 않습니다.

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python -m pytest -q -s tests/sipi/test_layered_stripline.py
```
