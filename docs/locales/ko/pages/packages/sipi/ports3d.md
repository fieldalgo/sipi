# 유한 영역의 3D TEM 포트 전자기장

[English](../../../../../packages/sipi/ports3d.md)

`sipi.ports3d.solve_tem_ports_3d`는 명시적인 정합 사면체 메시에서 균일하고
손실 없는 Maxwell 경계 문제를 풉니다. 평면 환형 포트 두 개에는 **국소 TEM
어드미턴스 경계**를 적용하고 나머지 외부 면은 PEC로 둡니다. 반환하는
`LineNetwork`는 두 TEM 모드로 투영한 전력 정규화 S입니다. 유한 영역의 계산
기본 기능이며, 완성된 비아 모델·자동 메시·일반 다중모드 방사 솔버는 아닙니다.

```python
import numpy as np
from galerkin.mesh import annulus_mesh
from galerkin.mesh3d import Mesh3D
from meshine.mesh import TriMesh
from meshine.extrude import extrude
from sipi.ports3d import TEMPort3D, solve_tem_ports_3d

base = annulus_mesh(.25e-3, 1e-3, 2, 24)
footprint = TriMesh(base.nodes, base.triangles,
    np.zeros(len(base.triangles), dtype=int), ["dielectric"], base.boundary_edges)
raw = extrude(footprint, [0., .005], divisions=4)
mesh = Mesh3D(raw.nodes, raw.tetrahedra)
faces = mesh.boundary_faces()
ports = []
for name, z in [("near", 0.), ("far", .005)]:
    selected = faces[np.all(mesh.nodes[faces, 2] == z, axis=1)]
    nodes = np.unique(selected)
    ports.append(TEMPort3D(name, selected,
        np.intersect1d(nodes, raw.boundary_nodes["inner"]),
        np.intersect1d(nodes, raw.boundary_nodes["outer"])))
result = solve_tem_ports_3d(mesh, ports=ports, frequency=[5e8, 1e9], eps_r=4.)
assert result.network.s.shape == (2, 2, 2)
assert result.power_balance.max() < 1e-8
assert abs(result.network.s[1, 0, 0]) < .02
```

## 입력과 경계의 의미

- 좌표는 m, 주파수는 양수이며 엄격히 증가하는 비어 있지 않은 Hz 배열입니다.
  `eps_r`는 유한한 양의 실수 스칼라이고 `mu_r=1`입니다. 분산·전도·텐서·요소별
  재료는 이 API에서 지원하지 않습니다.
- `TEMPort3D(name, faces, signal, ground)` 두 개를 줍니다. 이름은 고유해야 하며,
  면은 전역 노드 번호로 지정한 중복 없는 외부 삼각형입니다. 각 포트는 평면의
  연결된 환형 영역이고 경계 폐곡선이 둘이어야 합니다. 신호와 접지는 각각 서로
  다른 폐곡선 하나의 전체 노드입니다. 두 포트는 노드를 공유할 수 없고 PEC 벽은
  포트의 테두리에서만 만나야 합니다.
- 체적 메시가 연결되어야 합니다. 중복·퇴화 사면체, 미사용 노드, 잘못된 번호,
  비다양체 면을 거부합니다. [정전 API](capacitance3d.md)와 같이 모든 기하 겹침이나
  매달린 접합면을 탐지하지는 않습니다. 정합 메시 공급은 호출자의 책임입니다.
- 포트 표면 P1 Laplace 문제에서 신호 1 V, 접지 0 V를 지정합니다. 음의 접선
  기울기가 TEM edge 모드 `e_p`입니다. 전역 축으로 극성을 추정하지 않습니다.
  삼각형 꼭짓점 순서를 뒤집어도 지정한 신호/접지 극성은 유지됩니다.

시간 관례는 `exp(+j omega t)`입니다. 공유 galerkin의 Whitney edge curl-curl 및
질량 행렬에 포트 접선 질량 `Bp`를 더하여
`K-beta**2 M+j beta(B0+B1)`를 구성합니다. `beta=omega*sqrt(mu0*eps0*eps_r)`이며,
q번 입사는 `2j beta Bq e_q`, PEC edge 자유도는 0입니다. 국소 경계는 연속적인
균일 TEM 파동에는 정확하지만, 고차 모드마다 다른 전파 어드미턴스를 부여하는
완전한 도파관 포트 조건은 아닙니다.

## 결과와 적용 한계

`port_norm[p]=e_p.T@Bp@e_p`는 무차원입니다. 1 V 입사파의 전력은
`sqrt(eps/mu)*port_norm[p]/2`, 계산된 기준 저항은
`sqrt(mu/eps)/port_norm[p]` Ω입니다. 전력비의 제곱근으로 투영 S를 정규화합니다.
입력 포트 순서와 이름을 보존하며, 다른 실수 기준 임피던스는
`result.network.renormalized(...)`로 변환합니다. 원래 행렬에 50 Ω 표지만
붙여 사용하면 안 됩니다. 모든 반환 배열은 읽기 전용 사본입니다.

| 항목 | 주파수별 의미 |
|---|---|
| `linear_residual` | 자유도 선형 잔차의 Frobenius 노름 / 우변 노름 |
| `power_balance` | 전체 경계의 출사/입사 전력비와 1의 최대 절대 차이 |
| `reciprocity` | `S-S.T` 원소의 최대 절댓값 |
| `projected_unitarity` | `S.conj().T@S-I` 원소의 최대 절댓값 |
| `unprojected_port_power[f,q]` | 전체 출사 전력에서 TEM 투영 전력을 뺀 값 / q번 입사 전력 |

유한한 필드와 진단값을 요구하며 선형 잔차·전체 전력 잔차·상호성은 `1e-8`
이하여야 합니다. 실패 시 `ValueError`이며 부분 네트워크를 반환하지 않습니다.
TEM 투영 S만으로는 유니터리하지 않을 수 있습니다. TEM에 직교하는 경계 전력을
별도로 보존하며 **재료 손실로 해석하지 않습니다**. 원값을 잘라내거나 대칭화하지
않습니다. 이 대수적 검사는 메시 정확도·포트 위치 수렴·물리 오차 한계가 아닙니다.

검증은 반지름 0.25/1 mm, 길이 5 mm, eps_r=4, 1 GHz의 PEC 동축선입니다.
반경/각도/축 세분 `(1,12,2)`, `(2,24,4)`, `(4,48,8)`에서
`exp(-j beta length)` 대비 복소 전달 오차가 감소하고 최종 전달·반사 오차가
.02 미만이어야 합니다. 동일 메시의 독립 scikit-fem edge FEM 차이는 `1e-9`
미만, 회전·포트 순서·기하/주파수 동시 배율 변경의 S 차이도 `1e-9` 미만입니다.
외부 도체는 실제 PEC 벽이며, 개방 영역을 대신한 인공 외곽 경계가 아닙니다.

임의 전이·pad/antipad·via/stub·방사·고차 모드 차단 주파수·도체 손실 정확도를
이 시험으로 보증하지 않습니다. 새 기하는 독립 기준과 메시·포트 거리 수렴이
필요하며 작은 선형 잔차만으로 충분하지 않습니다. 앱 지원은 Python API와
별도입니다. 실행 의존성은 고정된 외부 galerkin/meshine과 NumPy/SciPy를
유지하며 scikit-fem은 시험에서만 사용합니다.

## 저장 입력과 공통 실행

`sipi.ports3d_document.TEMPorts3DDocument`가 `sipi.tem-ports-3d/1`을 저장합니다.
위 예제의 메시와 포트를 그대로 사용합니다.

```python
import json
from sipi.ports3d_document import TEMPorts3DDocument
from sipi.execution import normalize_saved, execute_saved

document = TEMPorts3DDocument(mesh, ports=ports, frequency=[5e8, 1e9], eps_r=4.)
text = normalize_saved(document.dumps())
replayed = TEMPorts3DDocument.loads(text).analyze()
np.testing.assert_allclose(replayed.network.s, result.network.s, rtol=0, atol=1e-10)
output = execute_saved(text, max_evaluations=2)
assert output["result"]["model"] == "bounded-homogeneous-3d-local-tem-admittance"
assert output["result"]["network"]["port_names"] == ["near", "far"]
json.dumps(output, allow_nan=False)
```

최상위 필드는 정확히 `schema`, `length_unit="m"`,
`unprescribed_boundary="pec"`, `port_boundary="local-tem-admittance"`, `mesh`,
`eps_r`, `frequency_hz`, `ports`입니다. `mesh`에는 `nodes`, `tetrahedra`만,
순서 있는 두 `ports` 항목에는 `name`, `faces`, `signal`, `ground`만 둡니다.
Mesh3D의 정수 변환 전에 원래 인덱스 타입을 검사합니다. 알 수 없거나 누락된
필드·중복 JSON 키·숫자 위치의 불리언·비유한 값·수치 범위 초과·다른 경계 이름은
거부합니다. 입력을 복사하며 `to_dict()`도 사본을 반환합니다. 정규화는 포트나
체적 필드를 풀지 않고 기하·위상을 검사합니다. 정합성이나 물리 정확도 인증은
아닙니다.

공통 실행은 **주파수 하나당 평가 한 번**으로 계산해 필드 계산 전에
`max_evaluations`를 검사합니다. 기존 입력 바이트 제한도 적용합니다. 이 제한은
희소 풀이의 메모리나 실행 시간을 제한하지 않으므로 호출자가 프로세스/Worker
격리와 취소를 제공해야 합니다. 솔버 오류를 성공한 부분 네트워크로 바꾸지 않고
전파합니다. 결과는 경계 모델 이름·네트워크·포트 노름·노드/사면체/edge 수와
여섯 일관성/전력 진단을 보존하고 체적 필드는 직렬화하지 않습니다. 이 엔진
계약만으로 앱의 고정 엔진을 변경하거나 Windows/Worker 지원을 확정하지 않습니다.
