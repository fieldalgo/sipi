# 유한 영역의 3D 정전용량

[English](../../../../../packages/sipi/capacitance3d.md)

`sipi.capacitance3d.extract_capacitance_3d`는 사용자가 명시한 사면체 유전체 영역에서
Maxwell 정전용량 행렬을 **패럿(F)**으로 계산합니다. galerkin의 P1 3D 조립과
접지된 희소 선형 풀이를 재사용합니다. 정전장 API이며 전송선 파라미터나 완전한
비아·전이 모델은 아닙니다. 기하 생성, L·R·손실·방사·임피던스·전파·S 파라미터를
추정하지 않습니다. `Capacitance3DDocument`로 엄격한 JSON 저장·재생을 제공합니다.
기하 편집기나 기존 앱의 지원을 뜻하지는 않습니다.

```python
from galerkin.mesh3d import box_mesh
from sipi.capacitance3d import extract_capacitance_3d
from sipi.constants import epsilon_0

mesh = box_mesh(.004, .003, .002, 4, 4, 4)  # metres
result = extract_capacitance_3d(
    mesh, eps_r=3.8,
    conductors={"top": mesh.boundary["z1"]},
    ground=mesh.boundary["z0"],
)
expected = epsilon_0 * 3.8 * .004 * .003 / .002
assert abs(result.C[0, 0] / expected - 1) < 1e-11
```

예제의 옆면 4개는 **절연 경계**입니다. 따라서 선형 전위와 이상적 평행판 식이
이 유한 영역에서는 정확합니다. 열린 공간의 유한 전극 프린징을 포함한 예제가 아닙니다.

## 입력과 경계의 의미

- `mesh`는 미터 단위의 정합 `galerkin.mesh3d.Mesh3D`입니다. 사면체 체적은 유한한
  양수여야 합니다. 중복 꼭짓점·요소, 사용하지 않는 노드, 비다양체 면을 거부하고
  공유 tagged-face 검사도 적용합니다. 모든 기하 교차나 hanging interface를 검출하는
  것은 아니므로 사용자가 정합 유전체 메시를 제공해야 합니다.
- `eps_r`는 유한한 양의 **실수** 스칼라 또는 사면체별 값입니다. 이 API는 텐서·복소·
  분산·전도성 재료를 지원하지 않습니다. 배열 순서는 메시의 사면체 순서와 같아야 합니다.
- `conductors`는 비어 있지 않은 이름과 서로 다른 정수 노드 집합의 매핑입니다.
  입력 순서가 행렬·장 열 순서를 정합니다. 각 신호 집합과 ground는 서로 겹치지 않아야
  합니다. PEC 등전위 노드를 지정하며 전극 표면·물리적 연결성을 자동 추론하지 않습니다.
- 메시의 모든 연결 성분에는 명시적인 `ground` 노드가 있어야 합니다. 지정하지 않은
  외곽면은 법선 전기변위가 0인 자연 Neumann 경계입니다. 외곽 박스를 접지하면 접지
  함체를 모델링하고 절연으로 남기면 다른 경계가 됩니다. 어느 쪽도 자동으로 무한 영역이
  되지는 않습니다.

## 결과와 수치 검사

열 `j`는 신호 `j`에 1V, 나머지 신호와 접지에 0V를 가합니다. 원래 풀이의 배열을
읽기 전용으로 보존합니다.

| 필드 | 의미 |
|---|---|
| `names` | 입력 순서의 신호 이름 |
| `C` | 1V 여기별 도체 반력 전하로 구한 전체 정전용량, F |
| `energy_C` | 별도 이산 평가 `U.T @ K @ U`, F |
| `potentials` | 노드별 단위 전압 기저, `(nodes, signals)`, V |
| `ground_charge` | 1V 여기별 접지 반력의 합, C |
| `num_tets` | 입력 사면체 수 |

`free_residual_relative`, `charge_balance_relative`, `energy_charge_relative`,
`symmetry_relative`는 각 최대 절대 차이를 `max(abs(C))`로 나눈 값입니다.
차이가 `1e-8`보다 크거나 비유한 값, 양수가 아닌 정전용량 고윳값, 같은 정규화
허용치를 넘는 양의 상호 성분·접지 전하가 있으면 거부합니다. 대칭화나 clipping으로
검사 실패를 숨기지 않습니다. 이 일관성 검사는 **연속장 오차 추정이나 작은 결합의
정확도 보장**이 아닙니다. 메시 조건수·재료 대비와 수렴을 확인해야 합니다.

## 검증과 제한

균일·경계 정합 층상 평행판은 해석적 선형 전위·직렬 용량과 상대 `1e-11`로 비교합니다.
비균일 두 전극장은 독립 scikit-fem 12.0.2의 사면체 P1 조립·풀이·에너지와 `1e-10`으로
대조합니다. 기하 배율에 따라 `C -> scale*C`, 재료 배율과 도체 순서 변경도 확인합니다.
두 내부 전극판이 있는 고정 접지 함체를 축당 8·16·24셀로 세분해 변화량 감소를
요구합니다. 이 추세가 최종 메시의 오차 범위를 정하는 것은 아닙니다.

목표 물리 문제에 맞게 경계를 선택하고 수렴시켜야 합니다. 무한 영역 외삽, pad/antipad
메시 생성, full-wave 기준, 실측 일치와 유효 주파수 범위는 여기서 확립하지 않았습니다.
정적 C 행렬만으로 비아·stub 동작을 지원한다고 주장할 수 없습니다.

## 명시적 메시 입력 저장

`sipi.capacitance3d_document.Capacitance3DDocument`는 schema
`sipi.capacitance-3d/1`, `length_unit="m"`, 필수
`unprescribed_boundary="insulating"`을 저장합니다. `mesh.nodes`는 좌표,
`mesh.tetrahedra`는 0부터 시작하는 정수 노드 번호입니다. `eps_r`는 양의 실수
스칼라 또는 사면체 순서의 배열입니다. `ground`는 노드 목록이며 `conductors`는
`{name, nodes}`의 **순서 있는 목록**입니다. JSON 키 정렬로 행렬 순서가 바뀌지
않습니다. 메시의 경계 태그는 저장하지 않으며 명시한 PEC 노드 집합만 전위를 정합니다.

```python
from sipi.capacitance3d_document import Capacitance3DDocument
from sipi.execution import normalize_saved, execute_saved

document = Capacitance3DDocument(
    mesh, eps_r=3.8, conductors={"top": mesh.boundary["z1"]},
    ground=mesh.boundary["z0"],
)
text = normalize_saved(document.dumps())
restored = Capacitance3DDocument.loads(text)
assert restored.dumps() == text
output = execute_saved(text)
assert output["result"]["model"] == "bounded-static-3d"
assert output["result"]["capacitance_f"][0][0] == restored.analyze().C[0, 0]
```

생성·복원 시 메시·재료·경계를 복사하고 검증하며 필드 연산자 조립이나 계산은
하지 않습니다. 알 수 없거나 누락한 키·버전·단위, 중복 객체 키·이름,
bool/소수 노드 번호, 비유한 수와 지수 overflow를 거부합니다. 자동 메시 생성,
단위 변환, 파일 접근, 코드 실행은 없습니다. `to_dict()`는 독립 복사본을 반환하고
`analyze()`는 직접 API와 같은 전체 `Capacitance3D` 결과를 반환합니다.

[공통 실행](execution.md)은 재생할 전체 입력을 보존하며 결과에서는 노드 전위와
메시의 중복 복사를 제외합니다. C·에너지 C(F), 1V 구동 시 접지 전하(C),
노드·사면체 수, 4가지 수치 일관성 비율을 반환합니다. 전송선 값을 추론하지 않습니다.
큰 메시가 입력 바이트 제한을 넘을 수 있습니다. 이를 늘려도 희소 계산의 메모리나
시간을 제한하지 못하므로 호출 측의 격리·자원 제한이 필요합니다. 이 명시적 메시는
파라미터 기하나 공차·역산 입력이 아닙니다. 기존 앱 후보는 정확한 엔진 버전을
갱신하고 별도로 검증한 뒤에 이 스키마의 지원을 주장해야 합니다.

## 공유 층상 메시: 닫힌 동축형 한계

기존 meshine extrusion으로 명시적인 정합 체적 메시를 만들 수 있습니다.
내반경 `a`, 외반경 `b`, 절연된 양단의 유한 동축형 영역 해석식은
`C = 2*pi*epsilon_0*sum(eps_i*length_i)/log(b/a)`입니다. 여기서 층은
축 방향이며 반경 방향 직렬 유전체가 아닙니다. 외원통은 접지이고
열린 끝의 프린징이나 파동 포트는 없습니다.

```python
import numpy as np
from galerkin.mesh import annulus_mesh
from galerkin.mesh3d import Mesh3D
from meshine.mesh import TriMesh
from meshine.extrude import extrude

base = annulus_mesh(.14e-3, .4e-3, 16, 128)
footprint = TriMesh(base.nodes, base.triangles,
                   np.zeros(len(base.triangles), dtype=int),
                   ["dielectric"], base.boundary_edges)
raw = extrude(footprint, [0, 1e-3], divisions=2)
coax = extract_capacitance_3d(
    Mesh3D(raw.nodes, raw.tetrahedra), eps_r=3.8,
    conductors={"inner": raw.boundary_nodes["inner"]},
    ground=raw.boundary_nodes["outer"],
)
exact = 2*np.pi*epsilon_0*3.8*1e-3/np.log(.4/.14)
assert abs(coax.C[0, 0]/exact-1) < .005
```

회귀는 균일·축방향 층상 유전체의 반경/각도 분할을 `(4,32)`, `(8,64)`,
`(16,128)`로 세분해 해석 오차 감소와 최종 0.5% 미만을 요구합니다.
별도로 `(8,64)`에서 축 분할 1·2·4의 C 범위가 최대 C 대비 `1e-4` 미만인지
확인합니다. 유한한 P1 사면체 분할에서는 축 방향 불변성에 작은 오차가
생길 수 있으므로 정확한 동일성을 가정하지 않습니다. 이 기준은 해당 시험
기하에 한정됩니다. 곡면 다각화로 영역 자체가 바뀌므로 고정 기하의 중첩 공간
단조성을 증명한 것은 아닙니다. 유한 비아·커넥터 전이나 일반 3D 기하 생성기를
구현한 예제로 해석하지 않습니다.

[얇은 격자/판 기준 셀](grid_plate.md)은 명시 기하·메시 정합·유한 경계를 보존하는 별도 정전장 도우미입니다.
