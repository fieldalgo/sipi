# 양면 접지 면별 금속의 IID 합격 평가

[English](../../../../../packages/sipi/two_ground_face_yield.md)

두 저장 계약으로 고정한 면별 도체 법칙과 원래 순서의 제조 표본을 평가한다.

| 모듈 / 문서 | 스키마 | 합격 사건 |
|---|---|---|
| two_ground_face_line_yield / TwoGroundFaceLineQuantityYieldDocument | sipi.two-ground-face-line-quantity-yield/1 | 단일 물리량의 포함 최소/최대 범위 |
| two_ground_face_pair_yield / TwoGroundFaceForwardPairYieldDocument | sipi.two-ground-face-forward-pair-yield/1 | 같은 행에서 두 쌍 여기 임피던스 범위를 모두 만족 |

입력은 [단일량 연구](two_ground_face_line_study.md) 또는
[쌍 연구](two_ground_face_pair_study.md)다. 단일량 단위는 기존과 같이 특성 임피던스
실수부는 ohm, 감쇠는 Np/m이며 감쇠 0도 유효하다. 쌍 값은 별도 Ic=0/Id=0 여기의
전체 전방 특성 행렬을 사용하고 독립 모드를 뜻하지 않는다. 공동 합격은 행별로
직접 세며 두 주변 합격 비율을 곱하지 않는다.

IID uniform 또는 normal 행만 허용한다. 한 normal 행 안의 변수 상관은 가능하지만
행 사이에는 독립을 가정한다. sweep/corners는 거부한다. 무효 기하·계산 실패를
포함한 모든 원래 표본을 순서와 분모에 남긴다. 미해결 행을 버리거나 교체하거나
알려진 불합격으로 취급하지 않는다. n개 중 k개 합격·u개 미해결이면 관측 비율 범위는
[k/n, (k+u)/n]이다. 보수적 Clopper–Pearson 구간은 기존 이항 꼬리 구현으로 미해결의
가능한 모든 완성을 포괄한다. 신뢰구간 수식이나 기준은 바꾸지 않는다.

이는 명시한 분포와 IID 가정에 조건부인 결과다. 수치·재료 분포·측정 오차는 포함하지
않으며 실측 생산 수율이 아니다. 예제의 네 표본은 실행 예시로, 제조 수율 주장의
충분한 근거가 아니다.

다음 예제는 입력 검증과 직렬화 왕복만 수행한다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_face_line_study import TwoGroundFaceLineQuantityStudyDocument
from sipi.two_ground_face_pair_study import TwoGroundFaceForwardPairStudyDocument
from sipi.two_ground_face_line_yield import TwoGroundFaceLineQuantityYieldDocument
from sipi.two_ground_face_pair_yield import TwoGroundFaceForwardPairYieldDocument

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1., roughness=dict(kind="smooth"))

faces = dict(zip(("bottom", "top", "left", "right"),
                 [metal(sigma) for sigma in (58e6, 35e6, 21e6, 45e6)]))

def source(paired):
    parameters = dict(width=.000435 if paired else .0006, plane_spacing=.002,
        eps_r=4., thickness=.00005, tan_delta=.003, box_width=.008)
    variables = [dict(name="width", lower=.00043 if paired else .00055,
                      upper=.00044 if paired else .00065)]
    if paired:
        parameters["gap"] = .00029
        variables.append(dict(name="gap", lower=.00028, upper=.00030))
    else:
        parameters["trace_height"] = .0007
    return ImpedanceStudyDocument("coupled_stripline" if paired else "offset_stripline",
        parameters, quantity="z_diff_forward" if paired else "z0", frequency=2e9,
        materials={}, mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05),
        sampling=dict(kind="uniform", count=4, seed=17, variables=variables))

reference = dict(kind="surfaces", bottom=metal(58e6), top=metal(21e6), sides=None, conductors={})
scalar = TwoGroundFaceLineQuantityStudyDocument(source(False), quantity="impedance_real",
    conductors=dict(signal=faces), reference=reference, ground_thickness=35e-6,
    panels_per_edge=64, ground_modes=128, interpolation_degree=16)
pair = TwoGroundFaceForwardPairStudyDocument(source(True),
    conductors=dict(positive=faces, negative=dict(zip(faces,reversed(list(faces.values()))))),
    reference=dict(reference, top=metal(58e6)), ground_thickness=35e-6,
    panels_per_edge=64, ground_modes=128, interpolation_degree=16)
scalar_acceptance = TwoGroundFaceLineQuantityYieldDocument(scalar, minimum=57., maximum=59., minimum_yield=.8)
pair_acceptance = TwoGroundFaceForwardPairYieldDocument(pair, acceptance={
    "differential_forward_impedance_real": dict(minimum=90., maximum=91.),
    "common_forward_impedance_real": dict(minimum=44.4, maximum=44.6)}, minimum_yield=.8)
for document in (scalar_acceptance, pair_acceptance):
    assert type(document).loads(document.dumps()).dumps() == document.dumps()
# Explicit field work: result = scalar_acceptance.analyze(max_evaluations=4)
```

생성과 정규화는 장을 풀지 않는다. 누락/추가 키·중복·비유한 값·호환되지 않는 입력
스키마는 거부한다. 계산 전에 전체 표본 수가 호출자 예산에 들어야 한다. 실패 행은
원 단계·typed 원인·확보한 전류/메시 기록을 유지한다. 이후 행은 계속 실행하고
중단은 전파한다. 수치가 합격 한도를 벗어난 판정 불합격과 계산 미해결은 다르다.
수율 목표 상태와 관계없이 미해결 행이 하나라도 있으면 저장 실행은 불완료다.

각 모듈의 `assess_two_ground_face_line_yield`와 `assess_two_ground_face_pair_yield`는
올바른 타입의 기존 연구를 장 계산 없이 평가한다. 표본 벡터·순서·개수·값·실패 구조를
검사한다. 이 구조 검사가 외부에서 만든 장 데이터의 진위를 인증하지는 않는다.
기존 전체 경계 계약은 별도로 유지한다. CLI·요청·기록·프로젝트는 모든 행을 유지하고
복원 시 다시 계산하지 않는다.

독립 유한 이항 꼬리 역산·SciPy exact 구간 대조·포함 경계·모든 미해결 완성·네 단일
물리량·상관된 무효 기하·예산·중단·엄격한 입력을 검증한다. 실제 단선/쌍의 seed-17
네 행은 등록한 2 GHz 면별 금속 연구를 사용하며 명시한 범위에서 분류와 이항 구간을
독립 재계산한다. 이는 문서화된 연구 세분 근거를 재사용하며 향후 임의 표본의 수렴을
주장하지 않는다. 전체 회귀·브라우저/플랫폼 일치·실측 대조는 선택한 소스/설치본 검사와 별개다.
