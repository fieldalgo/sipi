# 중심 간격을 유지하는 비대칭 쌍

asymmetric_coupled_microstrip의 study/design에서 fixed_pitch_m=p는 두 선로 중심의
수평 거리입니다. 각 행의 밑면 가장자리 간격은 다음처럼 유도합니다.

```
gap = p - left_width/2 - right_width/2
```

명목 반폭 합과 gap은 p와 상대 1e-12 이내로 같아야 합니다. left_width 또는
right_width 중 적어도 하나를 독립 변수로 두며 gap 직접 샘플링은 금지합니다.
두 폭과 다른 기하 변수를 함께 샘플링할 수 있습니다. 윗면 폭은 피치를 정의하지
않으며 기존 겹침·테이퍼·영역 잘림 검사는 그대로 적용합니다.

고정하는 것은 **중심 사이 거리**이지 각 중심의 절대 좌표가 아닙니다. 템플릿은
전체 밑면 폭 범위를 x=0에 맞추므로 서로 다른 폭이 변하면 두 중심이 함께 이동할
수 있습니다. 따라서 유한 상자 영향이 남습니다. 공기·상자 치수를 명시하고 대상
기하의 수렴을 확인하세요. 기존 같은 폭 템플릿의 gap=p-width와 중심 규칙은 유지합니다.

유한 범위의 모든 코너는 장 해석 전에 유효한 기하를 가져야 합니다. 무한 꼬리를
갖는 정규 표본에서 gap이 비양수가 되면 잘라내거나 다시 뽑지 않고 실패 행으로 남깁니다.
상관행렬은 독립 표본 변수에 적용하며 gap은 결정적으로 유도합니다. JSON 필드와
기존 canonical 입력은 그대로입니다. 옛 reader는 새 템플릿을 거부하므로 엔진·휠
해시를 함께 기록하세요.

```python
from sipi import asymmetric_coupled_microstrip, ImpedanceDesignDocument
from sipi.study import ImpedanceStudyDocument

parameters = dict(left_width=.4e-3, right_width=.65e-3, gap=.25e-3,
    substrate_height=.5e-3, eps_r=4, left_thickness=35e-6, right_thickness=50e-6,
    left_top_width=.32e-3, right_top_width=.55e-3, tan_delta=.02,
    air_height=6e-3, box_width=12e-3)
pitch = .775e-3
mesh = dict(edge_size=2e-6, far_size=.125e-3, grade=.1)
study = ImpedanceStudyDocument('asymmetric_coupled_microstrip', parameters,
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.35e-3, upper=.45e-3),
        dict(name='right_width', lower=.6e-3, upper=.7e-3)]),
    quantity='z_diff_forward', mesh=mesh, fixed_pitch_m=pitch)
for row in ImpedanceStudyDocument.loads(study.dumps()).sample_parameters():
    section = asymmetric_coupled_microstrip(**row)
    assert abs(section.traces[1].x-section.traces[0].x-pitch) < 1e-12*pitch
goal = ImpedanceDesignDocument('asymmetric_coupled_microstrip', parameters,
    variable='left_width', bounds=[.3e-3, .8e-3], target=100,
    quantity='z_diff_forward', tolerance=1, mesh=mesh, fixed_pitch_m=pitch)
result = ImpedanceDesignDocument.loads(goal.dumps()).solve()
assert abs(result.residual) <= 1 and abs(result.refined_residual) <= 1
```

목표는 [실수 전방 전류 입력 임피던스](asymmetric_pair.md)이며 별도 추적된 비대칭
고유모드가 아닙니다. 저장 목표는 같은 gap 제약을 사용하고 요청 메시·세분 메시 모두
허용 오차를 만족해야 합니다. 단일 변수 탐색은 수율 최적화나 제조 정확도 보장이
아닙니다. 고정 주파수 재료 지정도 기하 변수에 한해 함께 사용할 수 있습니다.

시험은 실제 중심 거리, 한쪽·양쪽 폭과 다른 변수의 조합, 표본·JSON 재생, 불변 사본,
유한/무한 범위의 잘못된 입력, 재료 공차 연결 및 실제 100±1 Ω 세분 역산을 확인합니다.
장 솔버와 앞선 독립 장 비교·수렴 관문은 바꾸지 않습니다.

[공차](study.md) · [비대칭 쌍](asymmetric_pair.md) · [English](../../../../../packages/sipi/asymmetric_pitch.md)
