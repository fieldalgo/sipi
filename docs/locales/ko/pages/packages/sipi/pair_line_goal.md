# 두 변수 전방 임피던스 목표

[두 변수 목표 저장](pair_line_goal_document.md)은 이름 있는 기하/재료 입력과 실행 실패를 보존합니다.

[English](../../../../../packages/sipi/pair_line_goal.md) ·
[한 변수 공통 전류 목표](common_forward_line_goal.md) ·
[전송선](line_model.md)

`sipi.pair_line_goal.seek_forward_pair_impedances`는 양의 유계 변수 두 개를
바꿔 복소 두 신호 선로의 **(Re(Zdd), Re(Zcc))**를 이 순서대로 맞춥니다.
factory는 양의 주파수 하나와 길이 0을 가진 `TransmissionLineDocument`를
반환해야 합니다. 주파수와 순서 있는 신호 이름은 고정합니다. 기하·재료·명시적
도체 법칙은 바꿀 수 있으며 물리적 유효성은 호출자가 확인해야 합니다.

Vd=V1−V2, Id=(I1−I2)/2, Vc=(V1+V2)/2, Ic=I1+I2를 사용합니다.
Zdd는 Ic=0인 전방 입사, Zcc는 별도로 Id=0인 전방 입사의 값입니다.
비대칭 비대각 결합을 유지하며 입사 전류 조건이 선로 전체에서 유지된다고
가정하지 않습니다. 목표는 실수부이며 절댓값·분리 고유모드·유한 선로의
종단 입력 임피던스가 아닙니다.

## 예제와 재현

길이는 m, 전도도는 S/m, 목표 허용치는 ohm입니다. 아래는 이미 검증한
초기점에서 요청 메시와 필수 세분 메시의 두 번 평가를 수행합니다.
검색까지 실행하려면 `initial=[.7e-3, .35e-3]`, `max_evaluations=64`로
바꿉니다. 해당 검색과 두 유한 외곽 확대 검사는 수치 시험에 포함됩니다.

```python
import numpy as np
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.pair_line_goal import seek_forward_pair_impedances

def line(width, gap):
    section = asymmetric_coupled_microstrip(
        left_width=width, right_width=.5e-3, gap=gap,
        substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6,
        box_width=24e-3, air_height=10e-3)
    def surface(conductivity, rms):
        return dict(conductivity=conductivity, relative_permeability=1.,
                    roughness=dict(kind='hammerstad', rms_m=rms))
    conductor = dict(kind='surface-boundaries',
        conductors={'positive': surface(58e6, .5e-6),
                    'negative': surface(35e6, 1e-6)},
        reference=surface(58e6, 0.), ground_thickness=35e-6)
    return TransmissionLineDocument(
        CrossSectionDocument(section, mesh=dict(
            edge_size=2.5e-6, far_size=.25e-3, grade=.075)),
        [1e9], materials={}, conductor=conductor, length=0.,
        schema='sipi.transmission-line/6')

goal = seek_forward_pair_impedances(
    line, [[.4e-3, .9e-3], [.2e-3, .6e-3]], [110., 40.],
    tolerances=[.25, .125],
    initial=[.6013576047896128e-3, .4103854246303812e-3],
    max_evaluations=2)
assert np.all(abs(np.array(goal.residuals)) <= goal.tolerances)
assert np.all(abs(np.array(goal.refined_residuals)) <= goal.tolerances)
assert len(goal.history) == 2
```

입력 스냅샷은 선택·세분 물리 모델을 보존합니다. 접근자는 새 문서를 복원하므로
복원본을 바꿔도 저장 입력은 바뀌지 않습니다. 보고서는 JSON 직렬화가 가능하지만
새 저장 입력 스키마나 factory 직렬화 형식은 아닙니다. 기존 스키마는 유지됩니다.

```python
import json
report = goal.to_dict()
json.dumps(report, allow_nan=False)
assert report['quantities'] == [
    'differential_forward_impedance_real', 'common_forward_impedance_real']
coarse = goal.document.to_dict()
fine = goal.refined_document.to_dict()
for key in ['edge_size', 'far_size', 'grade']:
    coarse['cross_section']['mesh'][key] /= 2
assert coarse == fine
assert goal.history[-1].stage == 'refinement'
```

## 검색과 실패 계약

bounds는 증가하는 양의 유한 수 쌍 두 개, 목표·절대 허용치는 각각 양의 유한 수
두 개입니다. 초기점은 닫힌 경계 안에 있어야 하며 생략하면 중간점입니다.
불리언 제어값은 거부하고 평가 예산은 2~10000의 정수입니다.

기존 bounded least-squares helper가 변수를 [0,1]로, 잔차를 허용치로
정규화합니다. 범위의 1% 중앙/단측 Jacobian probe와 xtol=ftol=1e-4,
gtol=1e-3을 사용합니다. 캐시된 변수 쌍은 재평가하지 않습니다. 캐시되지 않은
factory·입력 검증·추출·진단 시도는 실패와 Jacobian probe까지 모두 셉니다.
마지막 세분용 한 번을 예약합니다. 예산은 내부 계산 횟수·메모리·시간의 상한이
아니며 캐시는 전체 결과를 보관합니다.

선택 입력을 고정하고 edge size·far size·grade를 반으로 줄여 다시 평가하며
factory를 재호출하지 않습니다. 두 메시에서 두 목표가 모두 원래 절대 허용치를
만족해야 합니다. 초기점이 맞아도 세분하며 optimizer 성공 표시만으로 미달
목표를 수락하지 않습니다.

`ForwardPairGoalError`는 완료 `history`, `attempts`, `stage`,
`failed_parameters`, 가능한 `input_json`, `cause_type`과 원래 예외를
보존합니다. 제어값 오류는 factory 호출 전에 발생합니다. 해의 유일성·존재·
연속 응답·전역 최적성은 보증하지 않으며 rank가 부족해도 목표를 만족하면
수락할 수 있습니다. 전체 검색 영역의 물리적 유효성과 보고서를 확인하십시오.

## 검증과 한계

독립 power-dual modal 회로의 닫힌 임피던스와 알려진 두 변수 해를 사용하고
무손실·변수 단위 변환 한계를 검사합니다. 시험 전용 scikit-rf 2.2.0으로
modal 특성 임피던스를 1e-10 이내 비교합니다. 독립 balanced 2N 전압/전류
고유공간은 실제 전체 특성 행렬과 두 목표를 1e-10 이내 비교합니다.
후자는 추출된 RLGC를 재사용하며 독립 기하 추출 검증은 아닙니다.

위 1 GHz 비대칭 단면은 (.7,.35) mm에서 목표 (110,40) ohm, 허용치
(.25,.125) ohm으로 검색합니다. 요청/반분 메시 모두 목표를 만족하고 각 목표의
변화가 0.5% 이하여야 합니다. 세분 메시에서 box/air 24/10, 36/15,
48/20 mm가 같은 목표 허용치와 최소 영역 대비 0.5% 이내를 만족하고,
각 목표의 연속 절대 변화가 감소해야 합니다. 이는 별도 유한 사례 검사이며
API의 자동 외곽 검사·값의 단조 수렴·무한 영역 오차 상한이 아닙니다.

엄격한 입력, 고정 식별자, 캐시/예산, 원래 실패, 정체 미달, 세분 미달 및
저장 입력 재현을 회귀 검사합니다. 실측·full-wave 정확도, 제조 수율, 신규
플랫폼이나 전역 최적화 인증을 주장하지 않습니다.
