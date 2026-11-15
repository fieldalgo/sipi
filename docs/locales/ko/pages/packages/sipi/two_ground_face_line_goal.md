# 양면 접지 면별 금속 단일 변수 목표

[English](../../../../../packages/sipi/two_ground_face_line_goal.md)

`sipi.two_ground_face_line_goal`의 `seek_two_ground_face_line_quantity`는
[면별 금속 선로](two_ground_face_panel_line.md)를 기존 양수 단일 변수 구간 검색과
연결한다. 스칼라 `impedance_real`(Re(Zc), ohm) 또는 `attenuation`(Re(gamma), Np/m),
쌍 선로 `differential_forward_impedance_real` / `common_forward_impedance_real`
(Re(Zdd)/Re(Zcc), ohm)을 선택한다. 쌍 값은 별도 Ic=0/Id=0 여기의 전체 특성 행렬을
사용하며 독립 모드나 단자 임피던스가 아니다.

factory는 양수 주파수 하나·길이 0·스칼라 신호 하나 또는 순서 있는 쌍 신호를 갖는
명시 면별 금속 문서를 반환해야 한다. 전체 경계 문서는 거부한다. 두 끝점 모두 성공해야
하며 절대 허용오차 안의 끝점도 선택할 수 있다. 그렇지 않으면 잔차 부호가 구간에서
갈려야 한다. 이분법으로 연속성·단조성·유일성·전역 최적을 보장하지 않는다.
함수 자체는 직렬화하지 않으며 기존 전체 경계 목표는 그대로다.

다음 예제는 검색을 실행하지 않고 factory 입력을 검사한다.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument
from sipi.two_ground_face_line_goal import seek_two_ground_face_line_quantity

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1., roughness=dict(kind="smooth"))

def line(width):
    section = CrossSection([Layer("dielectric", .002, 4., tan_delta=.003)],
        [Trace("signal", 0., width, .0007, .00005)], .008, top="ground")
    faces = dict(zip(("bottom", "top", "left", "right"),
                     [metal(sigma) for sigma in (58e6, 35e6, 21e6, 45e6)]))
    return TwoGroundFacePanelTransmissionLineDocument(
        CrossSectionDocument(section, mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05)),
        [2e9], materials={}, conductors=dict(signal=faces),
        reference=dict(kind="surfaces", bottom=metal(58e6), top=metal(21e6), sides=None, conductors={}),
        ground_thickness=35e-6, length=0., panels_per_edge=128,
        ground_modes=128, interpolation_degree=16)

assert line(.0006).to_dict()["length_m"] == 0.
# Explicit field work:
# result = seek_two_ground_face_line_quantity(line, [.00055, .00065], 58.,
#     quantity="impedance_real", tolerance=.05, max_evaluations=40)
```

시도 예산 5..10000 중 실제 평가 세 번을 공동 세분·체적만·패널만 순서로 예약하고
이력을 보존한다. 검색 장 계산 전에 세 세분 입력을 모두 확인한다. 체적 세분은
해결된 edge/far/grade를 반감하고 전류 세분은 패널 수를 두 배로 한다. 주파수·신호
이름·접지 모드·보간 설정은 고정한다. factory를 다시 부르지 않고 동결한 선택 입력을
사용하므로 모든 면·코팅·거칠기·참조 금속·유전체 배치를 보존한다.

모든 세분 결과는 원 절대 목표를 만족해야 한다. nominal 대비 및 공동 세분과 각
단일 축의 상대 변화는 0.005 이하여야 한다. 이전 값이 분모이며 0은 0만 허용한다.
허용오차 완화·잘라내기·재시도로 실패를 성공으로 바꾸지 않는다. 호출 안에서 동일한
유전체 메시만 재사용하며 면별 전류는 명시적으로 계산한다. 시도 예산은 실행 시간·
메모리·행렬 계산량의 상한이 아니다.

`TwoGroundFaceLineQuantityGoalError.to_dict()`는 시도 수·이력·단계·실패 입력/변수·
원 typed 선로 오류와 확보한 전류/메시 관측을 보존한다. 실패도 시도로 세고 중단은
전파한다. 성공 결과는 선택/세분 문서와 진단을 모두 가진다. 제조 표본은 별도
[단일량 연구](two_ground_face_line_study.md)를 사용한다.

등록 물리 사례는 예제의 2 GHz 비대칭 높이 스칼라 선로, 폭 0.55–0.65 mm,
58 ohm 목표·0.05 ohm 허용오차·패널 128→256·시도 40회다. 독립 sqrt(Z/Y)와
sqrt(ZY)를 상대 1e-12로 확인한다. 동결한 선택 기하는 패널 256·접지 모드 256에서
메시 반감·유한 외곽 8/16/32 mm를 별도로 검사하고 R/L/C0·실수 임피던스·감쇠에
기존 상대 0.01 한도를 적용한다. 이 명시 해상도는 큰 상자에서 기본 모드 128을
인증하지 않는다. 네 quantity 독립근·실패 단계·예산·수렴 기준도 검증한다.
선택한 검사는 무한 영역·브라우저·다중 플랫폼·실측 정확도의 인증이 아니다.
실제 결과는 정확한 artifact 기록을 따른다.

[면별 금속 목표 저장](two_ground_face_line_goal_document.md)

[여러 주파수의 면별 금속 목표](two_ground_face_sampled_pair_goal.md)
