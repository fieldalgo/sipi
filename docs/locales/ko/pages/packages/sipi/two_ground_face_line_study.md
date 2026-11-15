# 양면 접지 면별 금속 단일량 표본

[English](../../../../../packages/sipi/two_ground_face_line_study.md)

`sipi.two_ground_face_line_study`의 `TwoGroundFaceLineQuantityStudyDocument`는
`sipi.two-ground-face-line-quantity-study/1`을 저장한다. 기존 순서 있는 단일량 표본
루프와 [면별 금속 선로](two_ground_face_panel_line.md)를 연결한다. 전체 경계 연구·
이전 스키마·기존 추출 기본값은 그대로다.

양수 주파수 하나에서 다음 네 양 중 정확히 하나를 선택한다.

| 입력 종류 | quantity | 의미 | 단위 |
|---|---|---|---|
| z0 | impedance_real | 스칼라 특성 임피던스의 실수부 | ohm |
| z0 | attenuation | 전파 상수의 실수부 | Np/m |
| z_diff_forward | differential_forward_impedance_real | 별도 Ic=0 여기의 Re(Zdd) | ohm |
| z_diff_forward | common_forward_impedance_real | 별도 Id=0 여기의 Re(Zcc) | ohm |

쌍 선로는 전체 복소 전방 특성 행렬을 사용하고 독립 대칭 전파 모드를 가정하지 않는다.
입력 label은 입력만 선택하며 원래 준정적 연구를 실행하지 않는다. 두 쌍 선로 여기를
하나의 결과에서 함께 계산하려면 [쌍 연구](two_ground_face_pair_study.md)를 쓴다.

엄격한 루트 키 일곱 개는 schema·study·quantity·conductors·reference·
ground_thickness_m·panel이다. Study/3 또는 /4의 순서 있는 기하/재료 변수·seed·
상관·fixed-pitch 제약·원래 표본을 유지한다. 면별 금속·코팅·거칠기 법칙은 표본 간 고정이다.
새 생성자의 기본 차수는 16이고 기존 기본값은 그대로다. nominal 입장은 장 계산 없이
확인하며 미지/누락 키·중복 키·비유한 값은 거부한다.

전체 표본 수가 max_evaluations(2..10000)에 들어야 장 계산을 시작한다. 중복·무효
표본도 각각 시도로 남긴다. 준비·추출·진단 실패는 단계와 확보한 입력/전류/메시 기록을
보존하고 이후 행도 실행한다. 중단은 전파한다. 잘라내기·삭제·재표본·재가중은 없다.
모든 행이 성공해야 기술 통계를 만들며 제조 수율 신뢰구간은 아니다. 임의 표본의
수렴이나 실측 정확도를 자동 인증하지 않는다.

공통 저장 실행·요청·기록·프로젝트·CLI는 같은 완료/불완료 의미를 유지한다.
기록/프로젝트 복원은 장 계산을 다시 하지 않는다. 다음 예제는 계산 없이 감쇠 sweep을 준비한다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_face_line_study import TwoGroundFaceLineQuantityStudyDocument

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1., roughness=dict(kind="smooth"))

source = ImpedanceStudyDocument("offset_stripline", dict(width=.0006,
    plane_spacing=.002, trace_height=.0007, eps_r=4., thickness=.00005,
    tan_delta=.003, box_width=.008), quantity="z0", frequency=2e9, materials={},
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05),
    sampling=dict(kind="sweep", count=3,
                  variables=[dict(name="width", lower=.00055, upper=.00065)]))
faces = dict(zip(("bottom", "top", "left", "right"),
                 [metal(sigma) for sigma in (58e6, 35e6, 21e6, 45e6)]))
document = TwoGroundFaceLineQuantityStudyDocument(source, quantity="attenuation",
    conductors=dict(signal=faces), ground_thickness=35e-6,
    reference=dict(kind="surfaces", bottom=metal(58e6), top=metal(21e6),
                   sides=None, conductors={}), panels_per_edge=64, interpolation_degree=16)
text = document.dumps()
assert TwoGroundFaceLineQuantityStudyDocument.loads(text).dumps() == text
assert document.samples().shape == (3, 1)
# Field work is explicit: result = document.analyze(max_evaluations=3)
```

검증은 네 독립 합성량·순서/상관된 무효 표본·재료 leaf·실패·기록 복원을 포함한다.
등록한 2 GHz 비대칭 높이 선로의 폭 0.55/0.60/0.65 mm에서 복소 sqrt(Z/Y)와
sqrt(ZY)를 1e-12로 대조하고 패널 64/128/256의 R/L/C0 변화를 0.01로 검사한다.
8 mm 상자는 접지 모드 128을 사용한다. 별도 양끝 폭의 메시 반감 및 유한 외곽
8/16/32 mm 검사는 접지 모드 256·패널 256을 명시하여 R/L/C0·실수 임피던스·
감쇠에 0.01 한도를 적용한다. 이전 스칼라 큰 상자의 128 모드 실패는 그대로이며
새 명시 해상도 검사가 큰 상자의 기본 설정을 인증하지 않는다. 실제 결과는 동반
기록을 따른다. 선택된 유한 사례로 무한 영역·임의 형상·브라우저·다중 플랫폼·실측을 인증하지 않는다.
