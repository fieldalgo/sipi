# 유한 영역의 3D 정전용량

[English](../../../../../packages/sipi/capacitance3d.md)

`sipi.capacitance3d.extract_capacitance_3d`는 사용자가 명시한 사면체 유전체 영역에서
Maxwell 정전용량 행렬을 **패럿(F)**으로 계산합니다. galerkin의 P1 3D 조립과
접지된 희소 선형 풀이를 재사용합니다. 정전장 API이며 전송선 파라미터나 완전한
비아·전이 모델은 아닙니다. 기하 생성, L·R·손실·방사·임피던스·전파·S 파라미터를
추정하지 않습니다. 이 API의 저장 JSON·UI 연결은 아직 없습니다.

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
