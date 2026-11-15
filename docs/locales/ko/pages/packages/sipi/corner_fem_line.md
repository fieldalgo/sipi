# FEM 형상 선로의 명시적 모서리 해상도

`CornerFEMShapeTransmissionLineDocument`는 기존 FEM 형상 선로와 별도 모서리
목표를 미터 단위로 보존합니다. 엄격한 JSON 스키마는
`sipi.corner-fem-shape-transmission-line/1`이며 키는 `schema`, `line`,
`corner_size`입니다. 목표는 유한 양수이고 해석된 edge 크기 이하여야
합니다. 불러오기와 정규화는 장을 풀지 않고 입력을 검사합니다.

```python
from sipi.templates import coupled_stripline
from sipi import (CrossSectionDocument,
                  FEMShapeTransmissionLineDocument,
                  CornerFEMShapeTransmissionLineDocument)
from sipi.execution import normalize_saved

section = coupled_stripline(width=.0004, gap=.0003, plane_spacing=.002,
                            eps_r=4., thickness=.00005, box_width=.008)
cross = CrossSectionDocument(section,
    mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1))
metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness=dict(kind='smooth'))
line = FEMShapeTransmissionLineDocument(cross, [2e9, 5e9], materials={},
    conductors=dict(positive=metal, negative=metal), reference=metal,
    ground_thickness=35e-6, length=.02)
saved = CornerFEMShapeTransmissionLineDocument(line, corner_size=2.5e-6)
assert normalize_saved(saved.dumps()) == saved.dumps()
# result = saved.analyze()
```

[기존 FEM 형상 선로](fem_shape_line.md)가 기하, 주파수 표본, 분산 재료,
경계 전체 금속, 기준 금속, 두께, 길이와 포트 기준을 정의합니다. 미분,
내부 확장장, 양의 에너지, 전류 보존과 표피 깊이 검사를 그대로 유지합니다.
명시적 모서리 목표는 메시 크기 제어이며 전류 솔버를 바꾸지 않습니다.
edge와 같은 값을 사용하면 기존 메시를 재현합니다. 진공과 재료 장은
같은 실제 메시를 사용합니다.

공통 실행기와 저장 요청은 특성량·모드 진단을 지원하고 풀이 전에 내포된
주파수 개수를 호스트 예산과 비교합니다. 결과는 전체 입력, 해석된 모서리
설정, 실제 메시 해시와 전류 관측을 보존합니다. 단계별 실패에는 전체
문서와 완료·부분 전류 근거를 남깁니다. 메시 크기 한도 초과는 실패이며
중단 신호는 전파합니다. 실행 기록이나 프로젝트를 다시 열어도 장을
다시 풀지 않습니다. 모서리 목표를 수정하면 현재 결과 연결을 해제하고
과거 기록을 보존합니다. 기록에는 실제 계산물의 해시를 명시하세요.

기존 FEM 선로 스키마는 내포된 mesh의 corner 키를 계속 거부합니다.
명시적 문서를 사용하세요. 기존 FEM 공차·역산·해상도 문서는 기존 선로
종류를 요구하며 새 문서를 암묵적으로 허용하지 않습니다.

검증은 기존 동작, 같은 값·절반 모서리 목표의 실제 쌍 선로, 정전용량
오프셋 24개, 내부 확장장 두 개, 독립 금속 전달 조합과 4포트 전파를
포함합니다. 유한 메시에서 전류의 일관성을 확인했다고 메시·외곽 수렴이
확인된 것은 아닙니다. 특히 작은 상호 저항은 항별 수렴을 별도로 확인해야
합니다. 이 메시 제어 API는 도체 손실 정확도나 새로운 플랫폼을 인증하지 않습니다.

[English](../../../../../packages/sipi/corner_fem_line.md)
