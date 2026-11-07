# 두 유전체 계면의 매립 coplanar 선로

[English](../../../../../packages/sipi/layered_coplanar_stripline.md)

`layered_coplanar_stripline`과 `coupled_layered_coplanar_stripline`은
[매립 coplanar 단면](coplanar_stripline.md)에 독립적인 두 유전체를 적용합니다.
신호 하나 또는 동일 폭의 수평 신호 쌍과 유한 폭 직사각형 측면 접지 두 개가
같은 높이·두께를 가집니다. 위·아래 접지면과 양측 접지는 모두 같은 기준 전위이며
신호 쌍 사이에는 접지를 넣지 않습니다. 길이 방향으로 균일한 준정적 단면입니다.

```python
from sipi import coupled_layered_coplanar_stripline, CrossSectionDocument

parameters = dict(width=.3e-3, gap=.3e-3, ground_gap=.3e-3, ground_width=.8e-3,
    lower_height=.4e-3, upper_height=.6e-3, lower_eps_r=3., upper_eps_r=5.,
    thickness=35e-6, lower_tan_delta=.01, upper_tan_delta=.03, box_width=6e-3)
mesh = dict(edge_size=5e-6, far_size=.125e-3, grade=.15)
section = coupled_layered_coplanar_stripline(**parameters)
document = CrossSectionDocument(section, mesh=mesh)
assert CrossSectionDocument.loads(document.dumps()).dumps() == document.dumps()
assert document.analyze().z_diff_forward > 0
```

길이 단위는 m입니다. `lower_height`는 아래 접지면에서 유전체 계면까지의 높이이며
모든 도체의 **아래면**이 이 계면에 놓입니다. `upper_height`는 계면에서 위 접지면까지의
높이이고 **구리 두께를 포함**합니다. 전체 높이는 `lower_height+upper_height`,
구리 위 여유는 `upper_height-thickness`이며 이 여유는 양수여야 합니다.
층 이름은 `lower`와 `upper`이고 각각 `eps_r >= 1` 및 음이 아닌 `tan_delta`를
받습니다. 유한 두께 전계에서는 두 계수를 평균하지 않습니다.

`width`·`gap`·쌍 전용 `ground_gap`·`ground_width`·선택적 신호 `top_width`·
`box_width`는 [균일 유전체 단면](coplanar_stripline.md)의 의미를 유지합니다.
신호는 사다리꼴일 수 있고 접지는 직사각형입니다. 양의 간격은 아래면 모서리
사이 값이며 넓어진 윗면도 겹치지 않아야 합니다. 정전기에서는 두께 0을 허용하되
기존의 두께 0 사다리꼴 제한을 유지합니다. 표면 손실의 양의 두께 및 skin-depth·
전류 보존 검사도 그대로입니다.

B=`lower_height+upper_height`일 때 생략된 상자 폭은 단일에서
`max(12*B, 4*width, width+2*gap+2*ground_width+4*B)`, 쌍에서
`max(12*B, 4*(2*width+gap), 2*width+gap+2*ground_gap+2*ground_width+4*B)`입니다.
절연 측벽의 외곽 영향을 확인할 때는 실제 접지 폭·간격을 고정하고 상자만 넓히세요.

## JSON·적층 공차·역산

기존 기하 JSON·study/1–4·design/1–3에서 두 이름을 사용합니다. 이전 판독기는
새 이름을 거부하므로 엔진 커밋을 기록하세요. 단일은 `z0`, 쌍은 `z_diff` 또는
`z_diff_forward`를 사용합니다. 기존의 실수 준정적 진단값이며 복소 손실 임피던스
목표는 아닙니다.

`fixed_plane_spacing_m`에서는 층 높이 하나만 표본화하고 나머지를 전체 높이에서
빼서 유도합니다. 위층 높이에 구리를 포함하는 정의도 유지됩니다. 쌍의
`fixed_pitch_m`은 폭 표본화 시 `gap=pitch-width`를 유도합니다. 두 제약을 함께
사용할 수 있으며 측면 접지는 `ground_gap`을 유지하도록 이동합니다. 명목 치수는
각 제약을 만족해야 합니다. 유한 범위는 계산 전 모든 모서리 입력을 검사하고,
무한 정규분포의 비물리 입력은 재추출하지 않고 실패 행으로 남깁니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import execute_saved, normalize_saved

study = ImpedanceStudyDocument("coupled_layered_coplanar_stripline", parameters,
    quantity="z_diff", mesh=mesh, fixed_pitch_m=.6e-3, fixed_plane_spacing_m=1e-3,
    sampling=dict(kind="normal", count=2, seed=19, correlation=[[1., .6], [.6, 1.]],
        variables=[dict(name="lower_height", mean=.4e-3, std=.02e-3),
                   dict(name="width", mean=.3e-3, std=.01e-3)]))
assert normalize_saved(study.dumps()) == study.dumps()
report = execute_saved(study.dumps(), max_evaluations=2)
assert len(report["result"]["rows"]) == 2
```

고정 주파수 스칼라·주축 재료 및 숫자 leaf 표본화는 `lower`와 `upper`를 독립적으로
지정합니다. 기존 [iid 수율 평가](yield.md)도 같은 저장 공차 입력을 사용하며
미해결 행을 유지합니다. 작은 예제 표본으로 제조 수율이나 실측 재료 정확도가
입증되지는 않습니다.

```python
from sipi import ImpedanceDesignDocument

goal = ImpedanceDesignDocument("coupled_layered_coplanar_stripline",
    dict(parameters, gap=.5e-3), variable="width", bounds=[.15e-3, .65e-3],
    target=100., quantity="z_diff", fixed_pitch_m=.8e-3,
    tolerance=.5, max_evaluations=24, mesh=mesh)
assert normalize_saved(goal.dumps()) == goal.dumps()
result = goal.solve()
assert abs(result.residual) <= .5 and abs(result.refined_residual) <= .5
```

한 변수의 구간 역산은 요청 메시와 세분 메시에서 모두 통과해야 합니다.
연속 다변수 최적화나 실측 생산 목표를 뜻하지 않습니다.

## 독립 검증과 범위

`tests/sipi/test_layered_coplanar_stripline.py`는 독립 scikit-fem의 구간별 복소·진공
P1 조립을 C/C_loss/C0 정규화 오차 1e−10으로 대조합니다. 동일 메시의 전체 유전율
배율은 1e−12, 재료가 같을 때 균일 템플릿 환원과 두께 0의 수직 반사는 0.5%
기준입니다. 반사는 위·아래 높이와 재료를 교환합니다. **유한 구리는 위층으로
들어가므로 이 교환만으로 반사 대칭이 되지 않습니다.** 대표 C/Z 메시 변화는
1.5%, 상자 두 배 변화는 0.5% 이내이고 상호성·양의 정부호도 검사합니다.

계면에 놓인 두께 0 도체와 멀리 있는 접지면·접지 끝의 해석 반공간 극한은
`eps_eff=(lower_eps_r+upper_eps_r)/2`,
`eps_loss_eff=(lower_eps_r*lower_tan_delta+upper_eps_r*upper_tan_delta)/2`입니다.
[CPW 타원적분 식](coplanar_stripline.md)에서 실효 실수 유전율로 C와 Z, 실효 손실로
C_loss를 얻습니다. 세 값 모두 2% 이내이고 메시 세분 시 각각 오차가 감소해야 합니다.
이는 독립 해석 검증용이며 두 재료의 실제 전계 계산을 대체하지 않습니다.

stitching via 접속·pad 전환·부유 기준 도체·방사·3차원 귀환 경로는 추가하지 않습니다.
기본 형상·메시로 임의 치수나 유전율 대비의 수렴이 보장되지 않습니다.
[제조 단면](manufacturing_sections.md), [공차](study.md), [역산](design.md)을 참고하세요.
