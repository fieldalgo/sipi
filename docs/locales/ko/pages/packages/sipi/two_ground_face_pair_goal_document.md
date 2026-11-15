# 면별 금속 쌍 선로 목표 저장

[English](../../../../../packages/sipi/two_ground_face_pair_goal_document.md)

`sipi.two_ground_face_pair_goal_document`의 `TwoGroundFaceForwardPairDesignDocument`는
`sipi.two-ground-face-forward-pair-design/1`을 저장한다.
[명시적 면별 금속 목표](two_ground_face_pair_goal.md)를 공통 저장 실행·불변 요청·
결과 기록·프로젝트·CLI에 연결한다. 전체 경계 스키마와 기존 문서는 그대로다.
새 물리 근사나 브라우저 인증이 아니라 입력 계약이다.

루트 키 열 개는 schema·study·conductors·reference·ground_thickness_m·panel·
targets_ohm·tolerances_ohm·initial·max_evaluations다. 미지/누락 키·중복 JSON 키·
비유한 숫자를 거부한다. 각 신호는 bottom/top/left/right 금속 법칙을 가지며
접지박과 고정 접지 도체는 [면별 선로 계약](two_ground_face_panel_line.md)을 따른다.
새 생성자의 기본 차수는 16이고 기존 문서 기본값은 바꾸지 않는다.

study/3 또는 /4 입력은 corners 표본·정확히 두 순서 있는 양수 범위 변수·쌍 선로
템플릿·양수 주파수 하나를 제공한다. 기존 fixed-pitch와 유전체 재료 leaf 연결을
재사용한다. nominal·초기값(또는 중간값)·네 경계 모서리에서 실제 선로와 미래 세분
세 가지 모두를 장 계산 없이 입장 검사한다. 내부 영역 전체의 유효성을 증명하는
것은 아니다. 고정 세분에서 물리적 면 이름과 금속 법칙의 연결을 보존한다.

직접 목표의 원래 기준을 유지한다. 실패 포함 4..10000 시도·세분 세 번 예약·두
원래 절대 목표 오차·상대 비교 0.005다. 호스트 예산이 저장 예산보다 작으면 계산
전에 거부한다. 목표에 최상위 선로 진단을 요청할 수 없다. 실패 단계·시도 입력·
이력·원래 면별 선로 오류를 보존하고 중단은 전파한다. 기록·프로젝트 복원은 계산하지 않는다.

다음 예제는 장 계산 없이 입력을 준비하고 저장·복원을 확인한다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_face_pair_goal_document import TwoGroundFaceForwardPairDesignDocument

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness=dict(kind="smooth"))

names = ("bottom", "top", "left", "right")
positive = dict(zip(names, [metal(s) for s in (58e6, 35e6, 21e6, 45e6)]))
negative = dict(zip(names, [metal(s) for s in (45e6, 21e6, 35e6, 58e6)]))
study = ImpedanceStudyDocument("coupled_stripline", dict(
    width=.00038, gap=.00028, plane_spacing=.002, eps_r=4.,
    thickness=.00005, tan_delta=.003, box_width=.008, trace_height=.000975),
    sampling=dict(kind="corners", variables=[
        dict(name="width", lower=.00035, upper=.0005),
        dict(name="gap", lower=.0002, upper=.0004)]),
    quantity="z_diff_forward", frequency=2e9, materials={},
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
quantities = ("differential_forward_impedance_real", "common_forward_impedance_real")
document = TwoGroundFaceForwardPairDesignDocument(study,
    conductors=dict(positive=positive, negative=negative),
    reference=dict(kind="surfaces", bottom=metal(58e6), top=metal(58e6),
                   sides=None, conductors={}), ground_thickness=35e-6,
    targets=dict(zip(quantities, [90., 44.5])),
    tolerances=dict(zip(quantities, [.1, .1])), initial=[.00038, .00028],
    panels_per_edge=128, interpolation_degree=16, max_evaluations=64)
text = document.dumps()
assert TwoGroundFaceForwardPairDesignDocument.loads(text).dumps() == text
# Field calculations are explicit: result = document.solve()
```

[고정 면별 금속의 제조 표본](two_ground_face_pair_study.md)
