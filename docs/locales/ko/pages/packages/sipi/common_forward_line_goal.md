# 유손실 공통 전류 순방향 임피던스 목표

[저장 목표 /3](common_forward_goal_document.md)은 지원 기하·재료 입력을 이 API에 연결합니다.

[English](../../../../../packages/sipi/common_forward_line_goal.md) | **한국어**

`common_forward_impedance_real`은 두 ordered 신호·고정 양의 주파수 하나에서
Re(Zcc)를 ohm 단위로 목표화합니다. 비대칭 기하·유전체·도체 법칙을 포함한
전체 복소 순방향 Zc를 사용합니다. u=[.5,.5]일 때 Zcc=u Zc u^T입니다.
좌표는 Vd=V1−V2,Vc=(V1+V2)/2,Id=(I1−I2)/2,Ic=I1+I2이며 입력면 Id=0에서
Vc=Zcc Ic,Vd=Zdc Ic입니다. 차동 전압은 일반적으로0이 아니며 하류 Id도0으로
유지된다고 가정하지 않습니다.

기존 [순방향 행렬](characteristic.md)의 상반성/수동성/조건수 기준을 유지합니다.
지정한 전류 입력 조건이며 독립 고유모드·절댓값·유한 종단 입력 임피던스가
아닙니다. 실수부 목표는 허수부를 제한하지 않습니다. 대칭 투영이나 모드 추적을
추가하지 않습니다.

예제는 중심 피치.95mm를 유지하며 왼쪽 폭을 바꿉니다. 두 신호선의 두께·전도도·
거칠기가 다르고 주파수는1GHz로 고정됩니다.

```python
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_goal import seek_line_quantity

def pair(width):
    section = asymmetric_coupled_microstrip(left_width=width, right_width=.5e-3,
        gap=.95e-3-(width+.5e-3)/2, substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6, air_height=10e-3, box_width=24e-3)
    def metal(sigma, rms):
        return dict(conductivity=sigma, relative_permeability=1.,
                    roughness=dict(kind='hammerstad', rms_m=rms))
    cross = CrossSectionDocument(section,
        mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075))
    return TransmissionLineDocument(cross, [1e9], materials={}, length=0.,
        schema='sipi.transmission-line/3', conductor=dict(kind='surface-boundaries',
            conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
            reference=metal(58e6, 0.), ground_thickness=35e-6))

goal = seek_line_quantity(pair, [.2e-3, 1e-3], 40.,
    quantity='common_forward_impedance_real', tolerance=.125, max_evaluations=24)
assert max(abs(goal.residual), abs(goal.refined_residual)) <= .125
mixed = goal.result.characteristic().mixed_mode()
assert goal.value == mixed.z_characteristic[0, 1, 1].real
assert abs(mixed.z_characteristic[0, 0, 1]) > 1e-3
selected_input = goal.document.dumps()
```

양의 범위·정확한 신호 순서/주파수·길이0·factory/검증/장/진단의 실제 시도 수와
원래 실패 snapshot은 [목표 API](line_goal.md)의 계약을 유지합니다. 선택한 입력을
고정한 뒤 edge size·far size·grade를 절반으로 줄이는 시도 하나를 예약하며
factory를 다시 부르지 않습니다. 원래/세분 값 모두 같은 절대 허용오차를 만족해야
합니다. 이분법은 연속성·단조·유일성·전역 최적의 증명이 아닙니다. 외곽 적절성은
별도로 확인해야 합니다.

```python
import json
import numpy as np
zc=goal.result.characteristic().z_characteristic[0]
u=np.array([.5,.5])
np.testing.assert_allclose(goal.value,(u@zc@u).real,rtol=1e-10)
current=np.array([.5,.5])  # Ic=1 A, Id=0 A at the launch plane.
voltage=zc@current
np.testing.assert_allclose((voltage[0]+voltage[1])/2,mixed.z_characteristic[0,1,1],rtol=1e-10)
np.testing.assert_allclose(voltage[0]-voltage[1],mixed.z_characteristic[0,0,1],rtol=1e-10)
report=goal.to_dict()
assert report['scope']=='bounded-single-parameter-common-forward-line-goal'
assert report['history'][-1]['stage']=='refinement' and report['evaluations']<=24
assert goal.unit=='ohm'
json.dumps(report,allow_nan=False)
```

기지 비직교 power-dual 변환을 적용한 독립 scikit-rf2.2.0 DistributedCircuit
모드는 Zc/Zcc를 상대1e-10 안에서 비교합니다. 별도 balanced2N 전압/전류
telegrapher 고유공간도 양의 위상 근과 같은1e-10 기준을 사용하며 제품의 Schur
제곱근과 독립입니다. 동일 RLGC의 비교이며 독립 기하 추출은 아닙니다. 대칭
공통 모드·손실0의 SPD 기하평균 한계, 차동 전압 결합, 엄격한 identity·예산·
고정 입력 세분·원래 오류도 검사합니다.

선등록40Ω 조건은 원래/세분/확장외곽 잔차<=.125Ω와 외곽 상대 변화<=.005를
요구합니다. 세분 메시에서 box/air를24/10mm에서36/15mm·48/20mm로 늘립니다.
요청 메시 edge2.5µm/far.25mm/grade.075를 모두 절반으로 줄여 세분합니다.
두 확장영역 모두 같은 기준을 통과하고 연속 절대 변화가 감소해야 합니다.
이는 유한 영역의 경향이며 무한 영역까지의 오차 상한은 아닙니다. 별도
이전 far.125mm(세분.0625mm)의24/10mm→48/20mm 시험은 외곽 메시 중
기존300000점 자원 상한을 넘어
미수락으로 보존합니다. 같은 이전 메시의 별도24→30→36mm 시험은30mm에서
39.9711677365Ω를 얻었지만36mm에서 같은 자원 상한을 넘었습니다. 전체 외곽
시험은 미수락이며 새 far 설정은 원래/세분 해석부터 다시 검증합니다. 오차 기준과
자원 상한은 완화하지 않았습니다. 별도40Ω
12/5mm→24/10mm 시험은 원래40.0317696120Ω·세분40.0497475740Ω가 절대
기준을 만족했지만 확장외곽39.8487339556Ω의 잔차−.1512660444Ω가 기준을
넘었습니다. 상대 변화.00501909826도.005를 넘었으므로 두 실패 모두 미수락으로
보존합니다. 별도 원래25Ω 시험은12/5mm 외곽·폭.2–1mm 양끝49.0350408845/36.8947052564Ω의 잔차 부호가 같아
2시도 뒤 원래 bracket 오류로 거부됐습니다. 이 조건은 미수락으로 보존하며
구간 내부 해가 없다는 전역 증명은 아닙니다. 성공으로 바꾸기 위해 허용오차를
완화하지 않았습니다.

이전 scalar/차동 목표6개의 보고서와 전체 RLGC 배열 해시는 소스/설치본에서
정확히 유지합니다. 기존 수치 탐색·장 추출·행렬 수식은 그대로이며 명시 물리량
선택에 공통 좌표1을 추가합니다. 저장 목표/공차 v1–2는 새 물리량을 계속 거부합니다.
선택 선로 입력은 저장할 수 있지만 Python factory는 직렬화하지 않습니다.
93스키마·37템플릿을 유지하며 실측/full-wave 정확도·연속 대역 보장·앱/플랫폼
업데이트는 추가하지 않습니다.
