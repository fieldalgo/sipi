# 모서리 제어를 명시한 FEM 해상도 비교

`assess_corner_fem_shape_line_resolution`은 corner FEM 선로, 세분 입력,
명시적으로 더 큰 열린 외곽 입력을 비교합니다. 저장 문서
`CornerFEMShapeResolutionDocument`는 `sipi.corner-fem-shape-resolution/1`의
`schema`, `line`, `outer_lines`, `refinement_factor`, `max_solves`, `tolerances`
여섯 키를 사용합니다. 모든 내부 선로는 명시적 corner FEM 문서입니다.
정규화는 장을 풀지 않습니다.

```python
from sipi import CrossSectionDocument, FEMShapeTransmissionLineDocument
from sipi import (assess_corner_fem_shape_line_resolution,
                  CornerFEMShapeTransmissionLineDocument)
from sipi.line_resolution import ResolutionTolerance
from sipi.templates import coupled_stripline

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness={'kind': 'smooth'})

line = FEMShapeTransmissionLineDocument(
    CrossSectionDocument(coupled_stripline(width=.0004, gap=.0003,
        plane_spacing=.002, thickness=.00005, eps_r=4., box_width=.008),
        mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1)),
    [2e9, 5e9], materials={},
    conductors={'positive': metal(58e6), 'negative': metal(35e6)},
    reference=metal(58e6), ground_thickness=35e-6, length=.02)
line = CornerFEMShapeTransmissionLineDocument(line, corner_size=2.5e-6)
outer = []
for width in (.016, .032):
    raw = line.to_dict()
    raw['line']['cross_section']['box']['width'] = width
    for key in ('edge_size', 'far_size', 'grade'):
        raw['line']['cross_section']['mesh'][key] *= .5
    raw["corner_size"] *= .5
    outer.append(CornerFEMShapeTransmissionLineDocument.from_dict(raw))
tolerances = {key: ResolutionTolerance(relative=.01, absolute=0.)
              for key in ('R', 'L_internal', 'L_external', 'C', 'G', 'C0')}
# Explicit execution (not performed by this field-free example):
# report = assess_corner_fem_shape_line_resolution(line, outer_documents=outer,
#     tolerances=tolerances, refinement_factor=.5, max_solves=4)
# saved_observations = report.to_dict()
from sipi import CornerFEMShapeResolutionDocument
from sipi.execution import normalize_saved
request = CornerFEMShapeResolutionDocument(line, outer_documents=outer,
    tolerances=tolerances, refinement_factor=.5, max_solves=4)
assert CornerFEMShapeResolutionDocument.loads(request.dumps()).dumps() == request.dumps()
assert normalize_saved(request.dumps()) == request.dumps()
```

내부 선로에는 기존 FEM 입력 검사를 그대로 적용합니다. edge, far, grade는
명시해야 하며 세분 비율은 0보다 크고 1보다 작아야 합니다. 외곽 입력은 최소
하나 필요합니다. 모서리 크기도 같은 비율로 줄입니다. 모든 외곽 입력은 그
정확한 모서리 크기와 세분 메시 설정을 유지해야 합니다. 열린 측면 또는 열린
상단 아래 마지막 층만 확장할 수 있습니다. 물리 경계면, 도체, 재료, 금속,
주파수와 포트는 고정합니다. 접지면 이동은 물리 변화이므로 거부합니다.

각 SI 물리량의 모든 행렬 항과 주파수에
`absolute + relative * max(abs(base), abs(actual))` 허용량을 적용합니다.
작은 상호 항에 대각 항 기반 바닥값을 넣지 않습니다. 메시 비교 기준은 기본
입력이고, 각 외곽 비교 기준은 세분 입력입니다. 문서·호스트 예산은 전체 선로
평가 횟수이며 각 평가에는 여러 장 풀이가 포함됩니다. 계산 전에 검사합니다.

계산을 마쳐도 불일치이면 `completed=True, accepted=False`로 보존합니다.
장 풀이 실패는 정확한 전체 corner 입력, 단계, 메시 식별과 완전하거나 부분적인
전류 근거를 남긴 뒤 멈춥니다. 중단 요청은 전파합니다. 요청·기록·프로젝트를
다시 열어도 재계산하지 않습니다. 부분 실패 결과에는 execution-record/2를
명시해야 합니다. 기존 버전 1의 거부와 평가 문서의 진단 요청 거부를 유지합니다.

기본 corner 결과는 기존 네 입력 FEM 관측과 대조하며 상호 R/내부 L 메시
변화가 기준을 넘는 **미수락**도 그대로 확인합니다. 더 작은 corner의 별도
네 입력 관측도 미수락입니다. 가장 큰 항별 R 변화는 메시 21.865%, 두 외곽
8.662%/8.121%로 기존 1% 허용량을 넘고 내부 L도 실패합니다. 독립 네트워크
항등식은 통과합니다. 모서리 설정을 더 작게 하는 것만으로 손실 수렴이
확보되지는 않습니다. 유한 비교는
절대 정확도, 점근 수렴, 모든 기하 또는 새 플랫폼 수락을 증명하지 않습니다.
일부 물리량만 선택하면 다른 물리량은 인증되지 않습니다.

[English](../../../../../packages/sipi/corner_fem_resolution.md)
