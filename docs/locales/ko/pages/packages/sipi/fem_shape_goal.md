# 검증된 FEM 전류의 유계 목표 역산

`seek_fem_shape_line_quantity`는 명시적인 `FEMShapeTransmissionLineDocument`를
반환하는 함수를 받습니다. 양의 유한 구간 안에서 변수 하나를 찾아 Re Zc
(`impedance_real`), Re gamma(`attenuation`), Ic=0의 Re Zdd
(`differential_forward_impedance_real`) 또는 Id=0의 Re Zcc
(`common_forward_impedance_real`)를 맞춥니다. 단일 목표는 신호 하나, 쌍 목표는 순서
있는 신호 둘을 요구합니다. 비대칭 결합을 유지하며 독립 전파 모드라고 가정하지 않습니다.

```python
from sipi import CrossSectionDocument, FEMShapeTransmissionLineDocument
from sipi import stripline, seek_fem_shape_line_quantity

metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness=dict(kind='smooth'))
def line(width):
    section = stripline(width=width, plane_spacing=.002, eps_r=4.,
                        thickness=.00005, box_width=.008)
    return FEMShapeTransmissionLineDocument(
        CrossSectionDocument(section, mesh=dict(edge_size=5e-6,
                             far_size=.0002, grade=.1)),
        [2e9], materials={}, conductors={'signal': metal}, reference=metal,
        ground_thickness=35e-6, length=0.)

# design = seek_fem_shape_line_quantity(line, [.00039, .00041], 70.35,
#     quantity='impedance_real', tolerance=.2, max_evaluations=12)
assert line(.0004).to_dict()['length_m'] == 0.
```

양의 주파수 하나·신호 이름과 순서·길이 0은 고정해야 합니다. 기하나 재료 파라미터는
달라질 수 있습니다. 함수 자체를 저장하거나 제조 분포를 추정하지는 않습니다.
양 끝점 계산이 모두 성공해야 하며 허용오차 안의 끝점을 선택할 수 있습니다. 그렇지
않으면 끝점 잔차의 부호가 달라야 이분 탐색합니다. 연속성·단조성·해의 유일성·전역
최적성을 증명하는 절차는 아닙니다.

선택한 입력을 동결한 뒤 메시 세분에 한 번의 시도를 예약합니다. 메시 설정을 풀어
`edge_size`, `far_size`, `grade`를 절반으로 하고 `min_angle`과 모든 물리 입력은
유지합니다. 세분할 때 생성 함수를 다시 부르지 않습니다. 두 결과가 같은 절대 목표
허용오차를 만족해야 하며, 명시 FEM API는 추가로
`abs(refined_value-value)/refined_value <= 0.005`를 요구합니다. 감쇠가 양쪽 모두
0이면 변화 0으로 보고, 0으로 바뀌는 비영 변화는 거절합니다. 원
`seek_line_quantity`의 기준은 바꾸지 않습니다. 이 검사는 외곽·물리 정확도 상한이
아닙니다.

예산은 실패를 포함한 생성·검증·추출·진단의 모든 시도를 셉니다. 내부 커패시턴스·속도
풀이는 별도로 세지 않으므로 시간·메모리 한도가 아닙니다. 재시도·잘라내기·미분 기준
완화·다른 전류 방법으로의 대체는 없습니다. KeyboardInterrupt/SystemExit는 전파합니다.

`FEMShapeLineQuantityDesign`은 선택·세분 선로 결과와 입력, 성공한 탐색 이력,
완료된 전류 기록 둘을 보존합니다. `FEMShapeLineQuantityGoalError`는 시도 횟수,
성공 이력, 실패 변수/입력, 단계, 원 예외 연결을 유지합니다. typed 선로 실패는 완료
또는 부분 전류를 `cause_details`에 남기며 진단·세분 수락 실패는 완료 전류를
`current_solver`에 보존합니다. 계산하지 않은 자료를 만들지 않습니다. 오류 사전은
저장 선로의 명시적 실패 문자열 표시에 따라 JSON으로 저장할 수 있습니다.

실제 단일·차동 폭 목표, 독립 행렬/스칼라 제곱근 특성량, 동결 입력 세분, 예산·실패
보존과 기존 목표 회귀를 검증합니다. 감쇠·공통 목표의 전달 시험은 관측한 전계를
명시적으로 재사용하며 새 물리 역산 실험은 아닙니다. 외곽 충분성·연속 대역·실측
정확도를 인증하지 않습니다. 기존 기준과 저장 문서는 그대로이며 전체 플랫폼 회귀와
저장형 생성 함수는 별도 작업입니다.

[English](../../../../../packages/sipi/fem_shape_goal.md)
