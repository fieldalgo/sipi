# 여러 주파수의 양면 접지 임피던스 목표를 JSON으로 저장하기

[English](../../../../../packages/sipi/two_ground_sampled_pair_goal_document.md)

`TwoGroundSampledForwardPairDesignDocument`는
`sipi.two-ground-sampled-forward-pair-design/1` 입력을 저장합니다. 템플릿·재료 입력을
[직접 유한 주파수 목표](two_ground_sampled_pair_goal.md)에 연결합니다. Python callable을
직렬화하거나 기존 저장 스키마를 변경하지 않습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_sampled_pair_goal_document import TwoGroundSampledForwardPairDesignDocument
from sipi.execution import normalize_saved

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00038, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9, materials={},
    sampling=dict(kind='corners', variables=[
        dict(name='width', lower=.00035, upper=.0005),
        dict(name='gap', lower=.0002, upper=.0004)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
goal = TwoGroundSampledForwardPairDesignDocument(source,
    frequencies=[2e9, 3.5e9, 5e9],
    conductors=dict(positive=metal, negative=metal),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=128, ground_modes=128,
    interpolation_degree=12,
    targets=dict(differential_forward_impedance_real=[90., 90., 90.],
                 common_forward_impedance_real=[44.5, 44.5, 44.5]),
    tolerances=dict(differential_forward_impedance_real=[.1, .1, .1],
                    common_forward_impedance_real=[.1, .1, .1]),
    initial=[.00038, .00028], max_evaluations=64)
text = goal.dumps()
assert normalize_saved(text) == text
```

예제는 장 계산 없이 입력을 준비하고 정규화합니다. `goal.solve()` 또는
`execute_saved(text, max_evaluations=64)`로 실제 탐색합니다. 길이는 m, 주파수는 Hz,
목표·허용오차는 Ω입니다. 이름으로 지정한 두 양마다 중간 주파수를 포함한 모든
주파수에 양의 유한 값을 하나씩 지정합니다. 원 연구 주파수는 첫 요청 주파수와
같아야 합니다. study/3·4의 모서리 표본에는 양의 유계 변수 두 개가 있어야 합니다.
재료 값 바인딩과 고정 기하 제약의 기존 의미를 유지하며 도체 전체 표면의 금속
법칙은 고정합니다.

정규화는 명목·초기/중간점·네 경계 조합의 전체 주파수와 세 가지 미래 세분 입력을
검사합니다. 장을 풀거나 모든 내부 점의 유효성을 보장하지 않습니다. 알 수 없는
필드·중복·누락·비유한 수·잘못된 배열을 거부합니다. 저장 시도 예산은 4~10000이며
호출자가 더 작은 예산, 부족한 입력 크기 제한이나 미지원 진단을 요청하면 풀이
전에 거부합니다.

직접 API의 전체 복소 순방향 목표, 캐시되지 않은 시도 수 계산, 세 번의 동결
세분 예약과 원래 절대·상대 0.005 기준을 그대로 사용합니다. 주파수별 재표본,
자동 재시도, 값 잘라내기나 연속 대역 보장은 없습니다. 실패 시 전체 주파수,
완료 이력·시도 수, 실패 입력·단계 및 구체적인 전류/유전체 원인을 보존합니다.
중단 요청은 전파합니다. 실패 목표는 결과가 null이고 근거는 오류 안에 있으므로
기존 버전 1 기록 계약을 사용합니다. 요청·기록·프로젝트를 다시 열어도 계산을
다시 실행하지 않습니다.

등록한 물리 저장 검사는 별도 33시도 직접 연구가 선택한 폭 .00043331845625629 m,
간격 .00028959075290925696 m를 명시 초기값으로 고정합니다. 원래 2·3.5·5 GHz,
90/44.5 Ω 목표와 0.1 Ω 허용오차를 유지하며 저장 풀이와 독립 구성한 직접
팩터리가 각각 네 번 시도한 전체 결과를 정확히 비교합니다. 이는 선택한 한
사례의 전달 검사이며 새로운 최적화나 독립 물리 정확도 기준이 아닙니다.
직접 연구의 원 행렬·세분·유한 외곽 근거는 별개로 보존합니다. 선택한 기하에
맞춰 참조 배열이나 허용오차를 바꾸지 않습니다.

소스·설치 artifact 검증은 브라우저·macOS·Windows·공개 배포 수락을 대신하지
않습니다. 정확히 고정한 공유 수치 기능이 필요하며 다른 장 계산법으로 우회하지
않습니다.

[요청 안에서 동일 전류 계수를 재사용](two_ground_current_reuse.md)하며 선로 시도 수와 수치 기준은 유지합니다.

같은 역산 요청 안에서만 성공한 동일 메시를 재사용합니다. 복사본 격리와 자원 한도는 [메시 재사용](two_ground_mesh_reuse.md)을 참고하세요.
