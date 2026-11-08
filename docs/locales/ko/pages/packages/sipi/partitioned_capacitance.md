# 분리된 유전체 영역의 정전용량

[English](../../../../../packages/sipi/partitioned_capacitance.md) | **한국어**

`extract_partitioned_capacitance_3d(mesh, *, eps_r=1., conductors, ground)`는
명시적으로 분리된 유전체 영역에서 기존 `Capacitance3D` 전체 Maxwell C[F] 결과를
반환합니다. 유한 두께 도체가 위아래 유전체를 나누면 바깥 영역이 신호 전극에만
접할 수 있습니다. 이 영역도 지정 전압으로 장이 정해집니다. 새 API는 전체 전극
연결에 전역 접지 기준이 있을 때 이를 지원합니다.

기존 [추출기와 저장 입력](capacitance3d.md)은 각 메시 연결 성분에 접지가 있어야
한다는 더 엄격한 조건을 유지합니다. 새 API는 별도이며 기존 저장 스키마를 바꾸거나
어떤 표면이 같은 도체인지 추론하지 않습니다.

```python
import numpy as np
from galerkin.mesh3d import Mesh3D, box_mesh

lower = box_mesh(1e-3, .8e-3, .4e-3, 2, 2, 2)
upper = box_mesh(1e-3, .8e-3, .3e-3, 2, 2, 2)
upper.nodes[:, 2] += .8e-3
offset = lower.num_nodes
mesh = Mesh3D(np.vstack([lower.nodes, upper.nodes]),
              np.vstack([lower.tets, upper.tets + offset]))
signal = np.r_[lower.boundary['z1'], offset + upper.boundary['z0']]
ground = lower.boundary['z0']
relative = np.r_[np.full(lower.num_tets, 3.8), np.ones(upper.num_tets)]
```

아래 유전체는 접지와 신호 사이에 있고 위 유전체는 같은 신호 전극에만 접합니다.
사이 틈은 제외한 금속이며 내부를 가상의 유전체 사면체로 채우지 않습니다.
호출자가 두 신호 표면을 명시적으로 묶습니다. 나머지 면은 절연이므로 위 영역의
정확한 해는 일정한 신호 전위이며 에너지 기여는0입니다. 자동 개방 경계가 아닌
명시적 유한 영역입니다.

```python
from sipi import extract_partitioned_capacitance_3d
from sipi.constants import epsilon_0

result = extract_partitioned_capacitance_3d(
    mesh, eps_r=relative, conductors={'signal': signal}, ground=ground)
exact = epsilon_0 * 3.8 * 1e-3 * .8e-3 / .4e-3
assert abs(result.C[0, 0] / exact - 1) < 1e-11
assert np.max(abs(result.potentials[offset:, 0] - 1)) < 1e-10
assert not result.C.flags.writeable
```

조립 전에 두 구조 조건을 검사합니다. 각 메시 연결 성분에는 적어도 하나의 지정
전극 노드가 있어야 하며, 모든 신호는 전극·유전체 성분 관계 그래프에서 접지에
이어져야 합니다. 그래프의 연결은 같은 유전체 영역에 접한다는 뜻이며 전기적
단락을 뜻하지 않습니다. 신호만 또는 접지만 접하는 영역도 해당 전극이 다른 영역을
통해 접지 기준을 가지면 유효합니다. 전극이 없는 유전체나 전역 접지에서 분리된
신호 집합은 거부합니다.

양의 유전율에서 장 에너지가0이면 각 연결 영역의 전위가 일정합니다. 관계 그래프의
조건에 따라 그 값은 접지0V로 이어지므로 전역 신호 정전용량은 양의 정부호입니다.
한 전극만 접하는 영역의 상수 전위도 이미 알려져 있어 미지 기준 전위가 생기지
않습니다. 부유 전극 전압·전하 조건·표면 묶음·기하를 추론하지 않습니다.

원래의 정합 양의 사면체, 유한 실수 노드, 비다양체·중복·미사용 노드, 양의 스칼라
또는 사면체별 상대 유전율, 비어 있지 않고 겹치지 않는 전극, 순서 있는 이름 조건을
유지합니다. 좌표 단위는 m입니다. 입력은 복사하고 결과 배열은 읽기 전용입니다.
j열은 j번째 신호를1V, 나머지 신호와 접지를0V로 둡니다. 결과는 C·에너지 기반 C·
전위·단위 구동의 접지 전하를 포함합니다.

수치 조립·해법·전하·에너지 본문은 기존 추출기와 byte 그대로 공유합니다. 원시 잔차·
전하 보존·에너지 일치·대칭·Maxwell 부호·양의 고유값 기준을 유지하며 대칭화·잘라내기·
유사역행렬을 추가하지 않습니다. 이번 단위에는 새 입력 스키마가 없습니다.

시험은 직렬 유전체 판을 포함한 아홉 해석 판·정전용량 회로 분할에서1e-11, 한 전극
영역의1V/0V 전위에서1e-10을 요구합니다. 균일 사례는 n2/3/4, 층상 사례는 정합
재료 경계와 n2/4/6을 사용합니다. 정확히 표현되는 구간별 선형 장의 분할 불변성
검사이며 임의 장의 수렴 검사는 아닙니다. 길이·유전율 배율, 전극 순열, 메시·성분
번호 변경은1e-10입니다. 독립 scikit-fem12.0.2의 세 P1 약형은 같은 메시에서
좌표 기반 재료·조립·해법을 별도로 사용하여 C·에너지·접지 전하·전위1e-10을 검사합니다.

상자와 절연 외곽을 고정한 검사이므로 개방 경계 극한을 보증하지 않습니다.
다른 기하는 메시·외곽 수렴 검사가 필요합니다. 기존 접지 사례는 정확한 출력 일치를
보이며 수정 전48개 스냅샷의 배열·진단 hash도 동일합니다. 입력 실패, 접지 기준 없는
집합, 기존 엄격 API/JSON, 독립 사본, 연산자·해법·원시 기준 실패를 검사합니다.
기준 도구는 시험 전용이며 선로 RLGC·인덕턴스·손실·전파·방사·실측 정확도·플랫폼
지원·의존성을 추가하지 않습니다.
