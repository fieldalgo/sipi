# 접지 격자 체적 위의 유한 두께 쌍 신호선

[English](../../../../../packages/sipi/volume_grid_pair.md) | **한국어**

`volume_grid_pair_cell`과 `extract_volume_grid_pair_capacitance`는 동일 폭의
직사각형 PEC 신호선 두 개와 사각 PEC 접지 격자의 두께를 명시하여 준비·계산합니다.
`VolumeGridPairCell`과 `VolumeGridPairCapacitance`는 기하와 `left, right` 순서의
**유한 셀 전체 Maxwell 정전용량 C[F]**를 보존합니다.
[단일 신호선 체적 API](volume_grid_strip.md)는 그대로 유지합니다.

```python
from sipi import volume_grid_pair_cell

inputs = dict(pitch=1e-3, grid_width=.5e-3, trace_width=.5e-3,
              trace_gap=.5e-3, height=.5e-3,
              top_clearance=1e-3, backside_depth=1e-3,
              ground_thickness=.125e-3, trace_thickness=.125e-3,
              eps_substrate=3.8, eps_above=1., eps_below=1.,
              transverse_periods=3, cells_per_pitch=4, cells_substrate=2,
              cells_above=4, cells_below=4, cells_grid=1, cells_trace=1)
cell = volume_grid_pair_cell(**inputs)
assert len(cell.inputs) == 19
assert cell.trace_metal_volume > 0 and cell.ground_metal_volume > 0
```

상자는 x=0..p,y=0..M*p이고 M은 홀수입니다. 폭 w인 두 신호선은 x 방향으로
지나며 y=M*p/2에 대칭 배치되고 양의 간격 s로 분리됩니다. y 구간은
[M*p/2-s/2-w,M*p/2-s/2]와 [M*p/2+s/2,M*p/2+s/2+w]이며 둘 다 z=h..h+ts입니다.
폭 g인 접지 띠는 정수 피치 선에서 교차하고 -tg..0을 차지합니다. 높이 h는
기판 간격이고 아래 경계는 -d, 위는 h+ts+a입니다. 금속 밖 z<0,0..h,h 위에
각각 명시한 상대 유전율을 적용합니다. 나머지 외곽 면은 절연·반사 경계이며
유한 상자를 자동 개방 공간으로 해석하지 않습니다.

19개 입력 모두 필수입니다. 치수와 세 유전율은 불리언을 제외한 유한 양의 실수입니다.
0<tg<d,g<=p,2*w+s<=M*p,홀수 M1..9,짝수 피치 셀 n4..32를 요구합니다.
반폭과 반간격은 p/n에 상대1e-12 반올림 범위에서 정합하며 요청값과 실제값을
보존합니다. 수직 정수 셀1..128 다섯 개는 -d..-tg,-tg..0,0..h,h..h+ts,
h+ts..h+ts+a를 분할합니다. 신호선 윗면과 위 여유는 표현 가능해야 합니다.
할당 전에 금속 제거 전 노드100000·사면체500000 예산을 검사합니다.

두 신호선과 접지 금속을 유전체 메시에서 제거하고 미사용 노드를 삭제·재지정합니다.
양의 사면체 체적 합은 상자에서 금속 체적을 뺀 값과 상대1e-12 안에서 맞아야 합니다.
세 재료 영역과 겹치지 않는 left/right/ground 표면은 명시적입니다.
[분리 영역 추출기](partitioned_capacitance.md)는 각 성분의 지정 전극과 전체
전극 관계의 접지 기준을 검사합니다. 미지 부유 도체 전위를 풀지는 않습니다.

```python
import numpy as np
from sipi import extract_volume_grid_pair_capacitance

result = extract_volume_grid_pair_capacitance(**inputs)
assert result.field.names == ('left', 'right')
c = result.capacitance_matrix_f
assert c.shape == (2, 2) and np.min(np.linalg.eigvalsh(c)) > 0
voltage = np.array([1., -1.])
stored_energy_j = .5 * voltage @ result.field.energy_C @ voltage
assert stored_energy_j > 0
assert not result.to_dict()['fields_included']
assert len(result.to_dict(include_fields=True)['potential_v_per_basis']) == len(cell.nodes)
```

j열은 신호선 j를1V, 나머지 신호선과 접지를0V로 둡니다. Maxwell C는 신호선
전압을 전하로 변환하며 비대각 성분은 음수입니다. `energy_C`는 이차형 정전장
에너지를, `ground_charge`는 두 기저의 접지 전하를 나타냅니다. 공통·차동 전압
벡터를 적용할 수 있지만 이를 자동으로 선로 전파 모드라고 해석하지 않습니다.

기하·재료·노드 배열은 독립 읽기 전용 복사본이며 `to_mesh()`는 태그를 추론하지
않는 독립 Mesh3D입니다. 간략 결과는 실제 폭·간격과 edge index, 제거 전·제거
개수, 접지 금속 체적, 두 신호선의 총 금속 체적, 유전체 체적을 포함합니다.
`include_mesh=True`는 배열을, 결과의 `include_fields=True`는 N×2 기저 전위를
추가합니다. 정전용량 속성도 독립 행렬을 반환합니다. 데이터클래스 직접 생성은
팩토리 검증을 대체하지 않습니다. 원시1e-8 기준·이름/형태·양의 정부호 C/에너지·
Maxwell 부호·지정 전위를 검사합니다. 이번 API는 버전 있는 저장 입력을 추가하지 않습니다.

독립 scikit-fem12.0.2의 네 P1 약형은 전체 C·에너지·접지 전하·전위 행렬을
상대1e-10에서 비교합니다. 좌표 재료 배정·조립·해법은 독립이며 정리된 메시는
공유합니다. 길이·전체 유전율 배율, 전극 순서 순열, 이차형 에너지, 완전 접지의
뒷면 차폐라는 해석적 불변식을 검사합니다. 기하 시험은 두 금속 체적·표면 노드·
재료 분할·미사용 노드 제거·횡방향 외벽에 닿는 신호선을 포함합니다. 사면체 대각선
때문에 두 자기 정전용량이 조금 달라질 수 있으므로 유한 메시에서 정확한 거울 대칭을
가정하거나 결과 행렬을 보정하지 않습니다.

선등록 연구는 p=1mm,g=w=s=.5p,h=.5p,tg=ts=.125p,기판3.8·외부1입니다.
M3·상하 .5p에서 메시 n8/16/24의 Frobenius 변화는4.5493%→**1.3864%**(<5%),
n8·상하 p에서 M3/5/7은2.2927%→**0.1741%**(<1%)입니다. M5·n8에서 위 여유
.5p/p/2p는1.9706%→**0.5993%**(<1%), 아래 여유 .5p/p/2p는
0.0002484%→**0.00003402%**(<0.1%)입니다. 바꾸지 않는 상하 외곽은 p이며
수직 셀은 p/n 간격을 유지합니다. 각 단계 변화이며 참오차 상한이나 통합 개방
경계 극한은 아닙니다. 다른 기하는 별도 평가해야 하고 임의 재분할 두께 단조를
보장하지 않습니다.

유한 경계 완전도체 정전장 셀입니다. 유한 전도도·거칠기·귀환 인덕턴스·선로
임피던스/RLGC·주파수 유효범위·전파·방사·실측 정확도를 추론하지 않습니다.
공유 솔버와 기존 API·스키마는 그대로이며 새 의존성·앱·플랫폼 지원은 없습니다.
