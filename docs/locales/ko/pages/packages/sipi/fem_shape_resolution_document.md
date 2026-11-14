# FEM 유한 분해능 요청 저장

FEMShapeResolutionDocument는 sipi.fem-shape-resolution/1을 사용합니다.
키는 schema, line, outer_lines, refinement_factor, max_solves, tolerances의
6개입니다. 중첩 선로는 명시적인 FEM 선로이며 기존 저장 형식·기본값은 유지합니다.
해석 전에 전체 입력·외곽·물리 조건과 예산을 확인합니다.

```python
from sipi import CrossSectionDocument, FEMShapeTransmissionLineDocument
from sipi import assess_fem_shape_line_resolution
from sipi.line_resolution import ResolutionTolerance
from sipi.templates import coupled_stripline

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness={'kind': 'smooth'})

line = FEMShapeTransmissionLineDocument(
    CrossSectionDocument(coupled_stripline(width=.0004, gap=.0003,
        plane_spacing=.002, thickness=.00005, eps_r=4., box_width=.008),
        mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1)),
    [2e9, 3e9], materials={},
    conductors={'positive': metal(58e6), 'negative': metal(35e6)},
    reference=metal(58e6), ground_thickness=35e-6, length=.02)
outer = []
for width in (.016, .032):
    raw = line.to_dict()
    raw['cross_section']['box']['width'] = width
    for key in ('edge_size', 'far_size', 'grade'):
        raw['cross_section']['mesh'][key] *= .5
    outer.append(FEMShapeTransmissionLineDocument.from_dict(raw))
tolerances = {key: ResolutionTolerance(relative=.01, absolute=0.)
              for key in ('R', 'L_internal', 'L_external', 'C', 'G', 'C0')}
# Explicit execution (not performed by this field-free example):
# report = assess_fem_shape_line_resolution(line, outer_documents=outer,
#     tolerances=tolerances, refinement_factor=.5, max_solves=4)
# saved_observations = report.to_dict()
from sipi import FEMShapeResolutionDocument
from sipi.execution import normalize_saved
request = FEMShapeResolutionDocument(line, outer_documents=outer,
    tolerances=tolerances, refinement_factor=.5, max_solves=4)
assert FEMShapeResolutionDocument.loads(request.dumps()).dumps() == request.dumps()
assert normalize_saved(request.dumps()) == request.dumps()
```
허용값의 SI 키는 R_ohm_per_m, L_internal_h_per_m, L_external_h_per_m,
C_f_per_m, G_s_per_m, C0_f_per_m입니다. 각각 relative와 absolute를 명시하며
직접 API의 항별 판정을 그대로 씁니다. 작은 항을 대각값으로 덮지 않습니다.
누락·추가 키, 중복·비유한 JSON, 물리 변경, 부족한 전체 선로 예산을 거부합니다.
analyze의 max_evaluations도 계산 전에 검사합니다.

공통 실행·요청·기록·프로젝트·CLI에서 사용할 수 있습니다. 계산이 완료됐지만
기준을 넘으면 실행 status는 complete, 결과 accepted는 false입니다. 계산 실패는
status=failed이며 부분 결과와 error에 같은 실패를 보존합니다. 원 입력·완료 또는
부분 전류·메시 식별 근거가 남으며 사용자 중단은 그대로 전달합니다. 선로용
특성량/모드 진단은 분해능 결과에서 거부합니다.

직접 API와 같은 실제 4선로 입력으로 검증합니다. 6양 전체는 상호 R/내부 L의 메시
변화 때문에 원1% 기준에 **미수락**이며 외곽 관측은 수락입니다. 저장 전달 검증은
이 실제 관측을 명시적으로 재사용하며 새 물리 풀이로 세지 않습니다. C/G만 선택한
수락은 그 두 양에만 적용되며 제외한 R/L 수락을 뜻하지 않습니다. 완료·미수락은 두 기록 버전에서 보존합니다. 부분 결과가 있는 실패는 명시적인
기록 형식2로 저장하며 프로젝트에서도 보존합니다. 기본 형식1은 기존대로
부분 실패 결과를 거부합니다. 형식2는 원 입력·종류·메시지와 typed 근거를 결합해
다른 입력의 실패를 끼워 넣지 못하게 합니다. 저장 자체가 정확도나
다른 OS의 검증을 뜻하지 않습니다.
