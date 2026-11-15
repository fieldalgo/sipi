# 면별 금속을 반영한 양면 접지 유한 주파수 역산

[English](../../../../../packages/sipi/two_ground_face_sampled_pair_goal.md)

`sipi.two_ground_face_sampled_pair_goal`의
`seek_two_ground_face_sampled_forward_pair_impedances`는 기존 유한 주파수·유계 탐색을
명시적인 면별 금속 두 접지면 선로에 연결합니다. 직접 Python API이며 callable을 직렬화하지
않습니다. 기존 [단일 주파수 목표](two_ground_face_pair_goal.md)와 저장 입력은 유지합니다.

다음 예제는 장 계산 없이 선로와 `solve()` 함수를 준비합니다.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument
from sipi.two_ground_face_sampled_pair_goal import seek_two_ground_face_sampled_forward_pair_impedances

frequencies = [2e9, 3.5e9, 5e9]
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))

faces = dict(zip(('bottom','top','left','right'),
    [dict(metal,conductivity=sigma) for sigma in (58e6,35e6,21e6,45e6)]))

def make_line(width, gap):
    section = CrossSection([Layer('dielectric', .002, 4., tan_delta=.003)],
        [Trace('positive', x=-(width+gap)/2, width=width, y=.000975, thickness=.00005),
         Trace('negative', x=(width+gap)/2, width=width, y=.000975, thickness=.00005)],
        .008, top='ground')
    return TwoGroundFacePanelTransmissionLineDocument(
        CrossSectionDocument(section, mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05)),
        frequencies, materials={}, conductors=dict(positive=faces,
            negative=dict(zip(faces,reversed(list(faces.values()))))),
        reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
        ground_thickness=35e-6, length=0., panels_per_edge=128, ground_modes=128,
        interpolation_degree=16)

def solve():
    return seek_two_ground_face_sampled_forward_pair_impedances(
        make_line, [[.00035, .0005], [.0002, .0004]], frequencies,
        [[90., 44.5]]*3, tolerances=[[.1, .1]]*3,
        initial=[.00038, .00028], max_evaluations=64)

assert make_line(.00038, .00028).to_dict()['frequency_hz'] == frequencies
```

 `solve()`를 호출하면
실제 탐색합니다. 길이는 m, 주파수는 Hz, 임피던스는 Ω입니다. 팩터리는 양의 유계
변수 두 개를 받아 순서가 고정된 신호 두 개, 길이 0, 요청한 증가 양주파수
2~64개를 그대로 갖는 선로를 반환해야 합니다. 탐색 중 신호 순서와 전류 제어값은
고정됩니다. 각 주파수에 양의 목표 두 개와 절대 허용오차 두 개를 지정합니다.
목표는 전체 복소 특성 행렬의 Ic=0·Id=0 별도 여기에서 얻는 Re(Zdd), Re(Zcc)입니다.
독립 전파 모드 임피던스가 아니며 비대칭 결합을 대칭으로 바꾸지 않습니다.

`max_evaluations`는 4~10000의 정수입니다. 캐시에 없는 전체 주파수 풀이 시도와
실패·최적화 탐색 시도를 모두 셉니다. 각 주파수를 새로운 제조 기하로 세지
않습니다. 선택 입력을 동결한 뒤 팩터리를 다시 부르지 않고 실제 세 번의 추가
풀이를 예약합니다. 유전체 세분은 edge·far·grade를 절반으로, 패널 세분은 패널 수를
두 배로, 결합 세분은 둘 다 변경합니다. 나머지 물리·전류 제어값은 고정합니다.
세 세분 입력의 자원 유효성도 최초 탐색 장 계산 전에 확인합니다.

각 세분 결과는 모든 주파수·두 여기의 절대 목표 허용오차를 각각 만족해야 합니다.
명목 대비 각 세분 및 결합 대비 두 단일 세분에 기존 상대 0.005 기준을 유지합니다.
실패한 주파수를 평균으로 숨기지 않으며 자동 재시도나 허용오차 완화가 없습니다.
유한 비교는 외곽 영역 적절성·연속 주파수 대역·해의 유일성·전역 최적값·실측
정확도를 보장하지 않습니다.

반환 결과에는 변수, 전체 주파수·목표·허용오차, 시도 이력, 정확한 선택·세분 입력,
실제 전류 근거와 유전체 메시 식별자를 남깁니다. `SampledPanelForwardPairGoalError`는
시도 수와 완료 이력, 실패 단계·입력 및 구체적인 두 접지면 원인 예외를 보존합니다.
중단 요청은 전파합니다. 시도 예산은 메모리나 실행 시간 제한을 대신하지 않습니다.

물리 등록은 기존 균일 epsilon_r=4·tan_delta=.003, 8×2 mm 영역과 높이 중앙의
50 μm 도체를 사용합니다. 첫 신호의 아래/위/왼쪽/오른쪽 전도율은
58/35/21/45 MS/m이고 둘째 신호는 그 배치를 뒤집습니다. 두 접지박은 58 MS/m,
명목 패널은 128·보간 차수는 16입니다.
2·3.5·5 GHz 모두 90/44.5 Ω±0.1 Ω, 폭 .35~.5 mm·간격 .2~.4 mm,
시작 .38/.28 mm 및 64시도 조건입니다. 선택·세 세분 결과를 독립 복소 행렬
제곱근과 균일 재료 불변식으로 검사합니다. 별도 외곽 16·32 mm는 선택 결합
기하·메시 제어를 유지하고 접지 모드를 512·1024로 지정합니다. R·내부/외부 L·
C·G·C0 모든 항에 상대 0.01·절대 0을 요구합니다. 균일 재료의 유전체 메시만
변경한 동일성은 해석적 C0 비례식의 성질이며 비균일 메시 수렴의 근거가 아닙니다.
원 기준의 실제 결과는 보존한 시험 기록을 따릅니다. 최적화 결과에 맞춘 새 기준
배열을 만들지 않습니다.

정확히 고정한 공유 개발 기능이 필요하며 다른 솔버로 우회하지 않습니다.
소스·설치 artifact, 브라우저 Worker, macOS·Windows의 검증 근거는 서로 구분합니다.

면별 금속·코팅은 동결된 모든 세분에서 이름 있는 물리 경계에 유지됩니다.
유전체 메시 문맥만 재사용하고 전체 경계 전류 캐시로 면별 전류 계산을 대체하지
않습니다. 기존 전체 경계 API와 수치 기준은 그대로입니다.
