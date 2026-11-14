# 검사된 FEM 선로의 예산 내 연속 세분

refine_fem_shape_line_resolution은 입력 메시를 단계적으로 세분하며 이력을
보존합니다. 선택한 모든 항·주파수가 연속 두 번의 인접 메시 비교를 통과한 뒤
모든 외곽 비교도 통과해야 selected_evaluation으로 선로를 선택합니다.
기존 선로·분해능 기본값은 바꾸지 않습니다.

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
assert len(outer) == 2
```
SI 허용값과 입력 규칙은 유한 분해능 API와 같습니다. 외곽 입력은 첫 세분
메시 설정을 사용합니다. 선택 단계에서는 그 메시 설정만 현재 세분값으로
교체하며 기하·금속·재료·주파수·길이·포트는 그대로 유지합니다. 최소 두 번의
비교와 모든 외곽 시도를 위한 예산을 포함해 계산 전에 검사합니다.

max_levels는 세분 메시 시도 수(2–8), max_solves는 원본·세분·외곽을 포함한
전체 선로 시도 수(4–16)입니다. 내부 전압·정전용량 풀이는 더 많습니다.
다음 메시를 풀기 전에 모든 외곽 시도의 예산도 남아 있어야 합니다. 완료 결과를
재사용하며 실제 계산은 원 전류·미분·재료·보존 검사를 매번 수행합니다.

종료 이유는 accepted, mesh-unaccepted, outer-unaccepted, budget-exhausted,
field-failed입니다. 세분 한도나 외곽 불일치는 계산 완료지만 미수락입니다.
예산 부족과 계산·준비 실패는 미완료입니다. 수락한 경우에만 원래 물리 영역의
selected_evaluation을 제공합니다. 한 번의 통과·떨어진 두 번의 통과·외곽 미검증으로
결과를 선택하지 않습니다. 입력·전류·항별 비교·typed 부분 실패를 보존하며
준비 실패는 시도한 원 입력을 남깁니다. 사용자 중단은 그대로 전달합니다.

실제 시험은 등록한 닫힌 쌍선로 2/3 GHz, edge5/2.5/1.25 μm와 전체 6양 항별1%,
절대값0을 사용합니다. 결과는 여전히 mesh-unaccepted이며 세 계산을 보존하고
아무 선로도 선택하지 않으며 외곽 계산도 시작하지 않습니다. 독립 선로 관계와
과거 실제 수치를 별도로 대조합니다. 제어 시험의 연속통과·외곽불일치·예산·
준비/계산실패 검증을 추가 물리 계산으로 세지 않습니다. 유한 통과는 절대 오차나
점근 수렴의 증명이 아니며 이 기능이 어려운 기하의 정확도를 자동으로 해결하지
않습니다.
