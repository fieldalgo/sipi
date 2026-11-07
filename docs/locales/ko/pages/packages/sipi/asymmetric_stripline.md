# 폭·두께가 다른 매립 차동 쌍

`asymmetric_coupled_stripline`은 두 접지면 사이의 균일 유전체에 비대칭 신호 도체
두 개를 배치합니다. `left_width`, `right_width`, `left_thickness`, `right_thickness`와
선택적인 `left_top_width`, `right_top_width`를 독립 지정하며 길이 단위는 m입니다.
유전체는 `eps_r`, `tan_delta`로 지정하고 측면 경계는 절연입니다.

## 기하와 임피던스 계약

`plane_spacing=H`는 동박을 포함한 전체 접지면 간 거리입니다. 각 도체의 **수직 중심**은
H/2이므로 바닥 높이는 `(H-thickness)/2`입니다. 두께가 다르면 바닥면 높이도 다릅니다.
왼쪽 도체가 positive, 오른쪽이 negative이며 전체 바닥 폭의 가로 범위를 x=0에 맞춥니다.

```
x_left  = -(gap + right_width)/2
x_right =  (gap + left_width)/2
pitch   = gap + (left_width + right_width)/2
```

`gap`은 바닥 폭의 가로 경계 간격이며 사다리꼴 면 사이의 최소 거리를 뜻하지 않습니다.
두께는 0이 가능하지만 gap과 폭은 양수입니다. 기존 taper·접촉·겹침·상자 잘림 검사를
유지하며 두 도체 모두 양쪽 접지면에서 떨어져야 합니다. 기본 상자 폭은
`max(12*H, 4*(left_width+gap+right_width))`입니다. 유한 상자 공차 연구에는 폭을 명시하고
외곽 수렴을 검사하세요. 이번 템플릿은 수직 offset·적층 유전체·불균일 접지면을 추가하지 않습니다.

좌우 폭·두께·윗폭이 같으면 기존 중앙 `coupled_stripline`과 정규 기하가 정확히 같습니다.
비대칭 입력에 교환 대칭이나 독립 even/odd 모드를 가정하지 않습니다. 저장 공차와 목표는
**`z_diff_forward`**만 허용합니다. 공통 입사 전류가 0인 전방 차동 전류에 대한 차동
전압의 비이며, 종단 임피던스나 진행 중 공통 전압이 0이라는 주장이 아닙니다.

## 저장·공차·역산

기존 기하/study/design 계약에 템플릿을 등록합니다. 양쪽 중 하나 또는 두 폭을 샘플링할 때
[두 폭 고정 피치 규칙](asymmetric_pitch.md)을 적용해
`gap = fixed_pitch_m - (left_width+right_width)/2`를 계산합니다. nominal 폭/gap이 이미
피치와 맞아야 하며 제약을 쓰면 gap을 독립 샘플링하지 않습니다. 윗폭은 피치 정의에
쓰지 않으며 고정 피치가 각 도체의 절대 중심 좌표를 고정하지는 않습니다.

sweep/corners/uniform/상관 normal의 기존 규칙을 유지합니다. 유계의 잘못된 모서리는
필드 전에 거부하고 normal의 잘못된 행은 잘라내거나 재표본하지 않고 실패로 남깁니다.
재료 study/3·/4는 `dielectric` 영역을 사용합니다. 기존 iid 수율과 단일 폭 목표 엔진이
저장된 전방 임피던스 입력을 처리합니다. 전손실 쌍 line-study/2는 별도 물리량인
`differential_forward_impedance_real`을 명시해야 합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.4e-3,
    plane_spacing=1e-3, eps_r=4., left_thickness=35e-6,
    right_thickness=50e-6, tan_delta=.02, box_width=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_stripline', parameters,
    quantity='z_diff_forward', fixed_pitch_m=.8e-3,
    sampling=dict(kind='uniform', count=2, seed=71,
        variables=[dict(name='left_width', lower=.28e-3, upper=.32e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze(max_evaluations=2)
assert result.failed == 0 and len(result.rows) == 2
for row in result.rows:
    left, right = row.document.section.traces
    assert abs((right.x-left.x)-.8e-3) < 1e-15
```

템플릿 목록은 31종이 되고 입력 스키마 필드와 저장 버전 42종은 그대로입니다.
이전 판독기는 새 이름을 거부할 수 있으므로 정확한 엔진/wheel 식별자를 입력과 보관해야
합니다. 새 런타임 의존성이나 앱/플랫폼 릴리스를 추가하지 않습니다.

## 검증 범위

유한 단면 fixture는 폭 .3/.5 mm, gap .4 mm, 접지면 간격 1 mm, 두께 35/50 um,
eps_r=4, tan_delta=.02, 상자 폭 6 mm입니다. 메시 5 um/.25 mm/grade .2에서
2.5 um/.125 mm/grade .1로 바꿀 때 C 행렬·전방 임피던스 변화가 1.5% 미만이어야 합니다.
fine 메시에서 상자 폭을 두 배로 늘릴 때 둘 다 .5% 미만이어야 합니다.
이 fixture의 이산화 검증이며 보편적인 정확도 보장은 아닙니다.

scikit-fem 12.0.2(BSD-3-Clause)의 독립 복소/진공 P1 조립을 같은 메시에서 수행해
C/C_loss/C0를 행렬 norm 기준 상대 `1e-10`에 비교합니다. 별도로 균일 유전체의
C=eps_r*C0, C_loss=tan_delta*C, 진공 기반 L과 전방 임피던스 스케일링을 `1e-12`에
검사합니다. gap 5H·box 32H에서 정규화한 교차 C는 `1e-4` 미만이고 자기 C는
각 고립 스트립 값에 1% 이내여야 합니다. 마지막 비교는 따로 생성한 메시 오차를 포함합니다.

저장 재료 binding/수율·전손실 PEC 표본을 독립 균일 복소 특성 행렬과 `1e-10`에 비교합니다.
고정 .8 mm 피치의 100-ohm 폭 목표는 요청/fine 및 외곽 확장 잔차가 1 ohm 이내이고
외곽 임피던스 변화가 .5% 미만이어야 합니다. 기하/엄격 입력 검사와 기존 비대칭 표면
쌍·관련 저장 계약도 회귀에 포함합니다. 실측 제조 정확도·임의 입력의 수렴·일반 3D
전이 거동을 입증하는 검증은 아닙니다.

[공차 연구](study.md) · [English](../../../../../packages/sipi/asymmetric_stripline.md)
