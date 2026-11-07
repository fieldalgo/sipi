# 유손실 단일 선로의 목표 역산

[English](../../../../../packages/sipi/line_goal.md) · [선로 입력](line_model.md) · [전파](propagation.md)

`sipi.line_goal.seek_line_quantity`는 사용자가 제공한 `TransmissionLineDocument`
factory의 양수 매개변수 하나를 바꿉니다. 지정한 표면 법칙을 포함한 도체·유전체의
추출 R/L/G/C로 다음 중 하나를 목표로 삼습니다.

| Quantity | 정의 | 단위 |
|---|---|---|
| `impedance_real` | 순방향 진행파 Zc의 실수부 | ohm |
| `attenuation` | 순방향 전파상수 gamma의 실수부 | Np/m |

Re(Zc)는 크기나 종단 부하와 다릅니다. 감쇠량은 길이당 진폭 감소이며 부정합도
포함하는 유한 선로 삽입손실과 다릅니다. 기존 `seek_impedance`는 실수 준정적
정의를 유지합니다. Zc 실수부 목표는 허수부를 제한하지 않으므로 보존된 복소
전파 결과도 확인하세요. 주파수는 고정된 양수 샘플 하나이며 대역 전체가 아닙니다.

```python
from sipi import CrossSectionDocument, stripline
from sipi.line_model import TransmissionLineDocument
from sipi.line_goal import seek_line_quantity

def line(width=.5e-3, loss=.02, metal=True):
    section = stripline(width=width, plane_spacing=1e-3,
        thickness=50e-6 if metal else 0., eps_r=4., tan_delta=loss, box_width=4e-3)
    conductor = (dict(kind='surface', conductivity=58e6, relative_permeability=1.,
        roughness_rms=.5e-6, ground_thickness=35e-6) if metal else dict(kind='perfect'))
    cross = CrossSectionDocument(section,
        mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
    return TransmissionLineDocument(cross, [1e9], materials={}, conductor=conductor,
                                    length=0., z_ref=75.)

width_goal = seek_line_quantity(lambda width: line(width=width), [.3e-3, .8e-3], 50.,
    quantity='impedance_real', tolerance=.5, max_evaluations=24)
assert abs(width_goal.residual) <= .5 and abs(width_goal.refined_residual) <= .5
assert width_goal.unit == 'ohm'
complex_z = width_goal.result.propagation().z_characteristic[0, 0]
assert width_goal.value == complex_z.real
saved_selected_line = width_goal.document.dumps()
```

factory는 기하 또는 재료 매개변수를 바꿀 수 있습니다. 각 문서는 신호가 하나이고
이름이 유지되며, 양수 주파수 하나가 고정되고 `length_m=0`이어야 합니다. bounds는
양수이고 factory 매개변수의 단위를 따릅니다. 차동 쌍과 일반 다도체 모드 목표는
거부합니다. 기하 대칭만으로 정확한 RLGC 대칭이나 기하 변화 사이의 모드 동일성을
보장할 수 없으며 이 API는 결합 성분을 투영해 없애지 않습니다.

양 endpoint가 모두 유효해야 합니다. 이미 허용오차 이내인 endpoint를 선택할 수
있고 그 외에는 잔차 부호가 목표를 끼워야 합니다. 이분법은 연속성·단조성·해의
유일성·전역 최적을 보장하지 않습니다. 임피던스 목표는 양수, 감쇠 목표는 0 이상이고
허용오차는 해당 물리량 단위의 명시적인 양수입니다. 선택 입력의 edge size·far
size·grade를 절반으로 줄이는 평가 하나를 예약합니다. 최소 각도와 모든 물리
설정은 유지하며 factory를 재호출하지 않고 고정된 선택 입력을 재사용합니다.
원래·세분 메시가 모두 같은 목표 허용오차를 만족해야 합니다. 실제 기하의 외곽
수렴과 모델 유효성은 별도로 확인해야 합니다.

```python
import json

loss_goal = seek_line_quantity(lambda loss: line(loss=loss, metal=False), [.01, .1], 1.,
    quantity='attenuation', tolerance=.001, max_evaluations=24)
assert max(abs(loss_goal.residual), abs(loss_goal.refined_residual)) <= .001
assert loss_goal.unit == 'Np/m'
report = loss_goal.to_dict()
assert report['evaluations'] == len(loss_goal.history) <= 24
assert report['history'][-1]['stage'] == 'refinement'
json.dumps(report, allow_nan=False)
```

결과는 원래·세분 선로의 전체 해석 결과, 재생 문서, 값·잔차·메시 변화와 완료된
모든 평가의 정확한 입력을 보존합니다. accessor 문서는 원본과 분리됩니다.
`to_dict()`는 유한 스칼라 결과와 입력을 담고 factory를 직렬화하거나 새 저장 목표
스키마를 만들지 않습니다. 탐색을 반복하려면 원래 factory와 제어값도 보존하세요.
선택된 재료 매개변수는 알고리즘 결과이며 실측 재료 fitting이 아닙니다.

`max_evaluations`는 3~10000 정수입니다. factory·정규화·추출·진단 실패도 시도
횟수에 포함합니다. 한 시도에 여러 내부 field solve가 있어 메모리·시간 상한은
아닙니다. 잘못된 제어값은 factory 전에 실패합니다. 이후 오류는 완료 `history`,
`attempts`, `stage`, `failed_parameter`, `cause_type`, 가능한 `input_json`을 담은
`LineQuantityGoalError`로 전달하며 원래 예외를 연결합니다. 실패 행을 성공 결과로
만들지 않고 세분 실패도 설계 성공으로 반환하지 않습니다.

유손실 균일 Cohn stripline 한계에서 폭 1%, 원래·세분 목표 잔차 0.1Ω를 요구합니다.
균일 PEC 선로의 gamma = j*omega*sqrt(mu*epsilon)*sqrt(1-j*tan_delta)를 이용해
감쇠 목표의 해석 tanδ 대비 0.5%와 양 잔차 0.001Np/m를 확인합니다. 유한 금속
폭 사례는 원래·세분·외곽 두 배의 목표 잔차 0.5Ω, 외곽 변화 0.5%를 요구합니다.
독립 scikit-rf Zc/gamma 비교는 동일 추출 RLGC로 상대 오차 1e−10을 요구하며
전파 계산 비교와 독립 field 정확도 검증을 구분합니다. 무손실 한계·실패 횟수·입력
보존도 검사합니다. 실측 제조 정확도·앱 또는 Windows 수락을 의미하지 않습니다.

```sh
python -m pytest -q tests/sipi/test_line_goal.py tests/sipi/test_line_model.py tests/sipi/test_propagation.py tests/sipi/test_design_documents.py
```
