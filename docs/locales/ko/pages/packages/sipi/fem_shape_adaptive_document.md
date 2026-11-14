# 예산 내 FEM 연속 세분 요청 저장

FEMShapeAdaptiveResolutionDocument는 sipi.fem-shape-adaptive-resolution/1이며
schema, line, outer_lines, tolerances, refinement_factor, max_levels,
max_solves의 7키를 사용합니다. 중첩 선로와 SI 허용값은 직접 API 규칙을 따릅니다.
파싱은 계산 없이 진행하며 기존 고정 분해능 형식과 기본값은 유지합니다.

```python
from sipi import CrossSectionDocument, FEMShapeTransmissionLineDocument
from sipi import refine_fem_shape_line_resolution
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
# report = refine_fem_shape_line_resolution(line, outer_documents=outer,
#     tolerances=tolerances, refinement_factor=.5, max_levels=2, max_solves=5)
# saved_observations = report.to_dict()
from sipi import FEMShapeAdaptiveResolutionDocument
from sipi.execution import normalize_saved
request = FEMShapeAdaptiveResolutionDocument(line, outer_documents=outer,
    tolerances=tolerances, refinement_factor=.5, max_levels=2, max_solves=5)
assert FEMShapeAdaptiveResolutionDocument.loads(request.dumps()).dumps() == request.dumps()
assert normalize_saved(request.dumps()) == request.dumps()
```
analyze 또는 공통 실행·요청·기록·프로젝트·CLI로 실행합니다. 호스트의
max_evaluations는 전체 선로 시도 수이며 시작 전에 검사합니다. 최소 두 번의
메시 비교와 모든 외곽 시도의 예산이 있어야 합니다. 이후 예산이 부족하면 완료한
계산을 남기며 자동으로 작업을 추가하지 않습니다. 원 전류·미분·재료·보존 검사도
유지합니다. 선택하지 않은 양을 수락하지 않으며 유한 차이의 통과는 절대 정확도
증명이 아닙니다.

세분 한도·외곽 불일치는 계산 완료지만 accepted=false이며 선택 선로가 없습니다.
예산 부족과 계산·준비 오류는 status=failed이고 부분 결과가 남습니다. 예산 부족은
결과 안 failure=None, 실행 error의 ResolutionBudgetExceeded로 구분하며 원 요청과
실행 제어값에 결합됩니다. typed 실패는 원 전류 근거와 정확한 실패 입력을 남기고
사용자 중단은 그대로 전달합니다.

기본 기록 형식1은 부분 실패 결과를 기존대로 거부합니다. 명시적인 형식2는
지원하는 typed/예산 실패를 보존하며 프로젝트 왕복도 지원합니다. 이 검사는
구조와 원 입력의 결합을 확인할 뿐 가져온 기록의 물리적 타당성을 인증하지 않습니다.

실제 저장 시험은 등록한 닫힌 쌍선로의 원본·half·quarter를 계산합니다. 원 전체6양
항별1%에서 여전히 mesh-unaccepted이며 선로 선택·외곽 계산을 하지 않습니다.
직접 API와 수치가 같은지, 독립 선로 관계가 맞는지 확인합니다. 전달 시험의 예산·
typed 실패는 실제 관측을 명시 재사용하며 추가 물리 계산으로 세지 않습니다.
