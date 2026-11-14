# 검사된 FEM 선로의 유한 메시·외곽 비교

`assess_fem_shape_line_resolution`은 FEM 선로를 명시적인 메시·외곽 비교에
연결합니다. 기존 계산법과 수치 기준은 유지하며 절대 정확도를 인증하지 않습니다.

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
assert len(outer) == 2
```

예산은 원본·세분·각 외곽의 전체 선로 시도를 셉니다. 내부 전류 미분·정전용량·
전압 풀이 횟수는 이보다 많습니다. 모든 입력과 예산은 계산 전에 확인합니다.
edge_size, far_size, grade를 명시해야 하며 세 인자만 (0,1) 비율로 줄입니다.
각 계산은 원 전류·미분·유한차분·재료·전류 보존 검사를 그대로 수행합니다.

외곽 입력은 세분 메시 설정과 도체·계면·층 수·재료·금속·주파수·길이·포트를
그대로 유지해야 합니다. 열린 측면의 폭이나 열린 상단의 마지막 층 두께만
늘릴 수 있으며 줄이거나 접지면을 옮길 수 없습니다. 메시 비교는 원본과 세분,
외곽 비교는 각 외곽과 세분 사이에서 수행합니다. 외곽끼리의 순서 비교가 아닙니다.

선택한 모든 행렬 항·주파수에 `absolute + relative * max(abs(reference),
abs(actual))`를 적용합니다. R은 Ω/m, 내부·외부 L은 H/m, C/C0는 F/m, G는 S/m입니다.
작은 상호항의 분모 바닥이나 대각값 척도는 없습니다. 두 허용값이 0이면 정확히
같아야 합니다. 미선택 양은 판정하지 않습니다. 계산이 끝나도 차이가 크면
completed=True, accepted=False이며 계산 실패로 위장하지 않습니다.

결과는 변경 불가 비교 배열과 정확한 입력을 보존합니다. to_dict()에는 완료한
각 선로의 전류 근거도 들어갑니다. 계산·비교 예외는 후속 시도를 멈추고 완료분,
단계·입력·종류·메시지를 남깁니다. FEM 오류는 원 전류·부분 관측도
failure.details에 보존합니다. 반환된 details를 바꿔도 내부 기록은 바뀌지 않습니다.
사용자 중단은 그대로 전달합니다.

검증은 닫힌 쌍선로 2/3 GHz, 8 mm 원본·16/32 mm 외곽과 사전 등록한 항별 1%,
절대값 0 기준을 사용합니다. 실제 관측을 기록하고 균일 유전체·도금 금속·독립
회로 관계를 확인하며, 그 결과를 명시적으로 재사용하여 불일치와 단계별 실패를
검증합니다. 유한 관측은 점근 수렴·약한 모드·임의 기하/주파수·실측·다른 OS의
정확도 증명이 아닙니다. 일반 중첩 메시 기능은 추가하지 않습니다.

등록한 원본→세분 메시 입력은 **미수락**입니다. 작은 상호 R 변화는 최대 약
6.57%, 내부 L은 약 2.93%로 원1% 기준을 넘었습니다. 두 외곽 비교는 이 표본에서
수락됐습니다. 시험은 이 미수락 결과의 보존을 검사하며 메시 충분성을 주장하지
않습니다. 처음 전체수락을 기대했던 실패 기록을 보존했고 물리 입력·허용값은
바꾸지 않았습니다.
