# 유한 두께 접지 격자 위의 얇은 트레이스

[English](../../../../../packages/sipi/thick_grid_strip.md) | **한국어**

`thick_grid_strip_cell`은 유한 영역 사면체 기하를 준비하고,
`extract_thick_grid_strip_capacitance`는 **전체 정전용량 C[F]**를 계산합니다.
`ThickGridStripCell`과 `ThickGridStripCapacitance`가 기하와 장 결과를 보존합니다.
기존 [얇은 격자 모델](strip_grid.md)은 변경하지 않았으며, 세 유전체 영역과
공유 [3D 정전용량 추출기](capacitance3d.md)를 사용합니다.

```python
from sipi import thick_grid_strip_cell

inputs = dict(pitch=1e-3, grid_width=.5e-3, trace_width=.5e-3,
              height=.5e-3, top_clearance=1e-3, backside_depth=1e-3,
              ground_thickness=.25e-3, eps_substrate=3.8, eps_above=1., eps_below=1.,
              transverse_periods=3, cells_per_pitch=4, cells_substrate=2,
              cells_above=4, cells_below=3, cells_grid=1)
cell = thick_grid_strip_cell(**inputs)
assert cell.to_dict()['removed_num_tets'] > 0
assert cell.relative_permittivity.shape == (len(cell.tets),)
```

x 길이는 피치 p, y 폭은 홀수 M개의 피치입니다. 폭 g인 접지 띠가 정수 피치
x/y 선에서 교차하며 -t<=z<=0을 차지하고0V입니다. 중앙의 폭 w인 얇은 트레이스는
z=h에서 x 전체를 지나며1V입니다. 아래 경계는 -d, 위는 h+a입니다.
z<0은 eps_below,0<z<h는 eps_substrate, z>h는 eps_above를 사용합니다.
나머지 면은 절연·반사 경계이며 자동 개방 경계나 파동 포트가 아닙니다.

16개 입력 모두 필수입니다. 치수는 SI 단위의 유한 양수, 상대유전율은 양수입니다.
0<t<d, g<=p, w<=M*p, 홀수 M1..9, 짝수 피치 분할4..32를 요구합니다.
네 수직 구간은 각각 정수1..128개로 나눕니다. `cells_below`는 -d..-t,
`cells_grid`는 -t..0, `cells_substrate`는0..h, `cells_above`는 h..h+a입니다.
불리언은 거부하며 두 반폭은 상대1e-12 반올림 오차 안에서 측면 격자와 정합해야
합니다. 요청 폭과 실제 정합 폭을 별도로 보존합니다.

할당 전 금속 제거 전 메시의 노드100000·사면체500000 예산, 유한 양의 상자 체적과
표현 가능한 상단 여유를 검사합니다. PEC 체적의 사면체를 제거한 뒤 미사용 노드를
삭제하고 인덱스를 다시 매깁니다. 금속을 임의 유전체로 채우지 않습니다. 남은 각
사면체 체적은 양수이며 합은 상자 체적에서 금속을 뺀 값과 상대1e-12 안에서 맞아야
합니다. 표면 접지 노드는 명시적입니다. 완전한 접지판이 유전체를 두 연결 성분으로
나누는 경우에도 각각 접지되며 기존 추출기의 연결 성분 검사를 유지합니다.

```python
from sipi import extract_thick_grid_strip_capacitance

result = extract_thick_grid_strip_capacitance(**inputs)
assert result.capacitance_f > 0
compact = result.to_dict()
assert compact['stored_energy_j_at_one_volt'] == .5*result.field.energy_C[0, 0]
assert not compact['fields_included']
expanded = result.to_dict(include_fields=True)
assert len(expanded['potential_v_at_one_volt']) == len(result.cell.nodes)
```

`cell.inputs`는 새16키 스냅샷입니다. 기하·전극·사면체별 유전율은 복사된 읽기 전용
배열이고 `to_mesh()`는 면 태그를 추론하지 않는 독립 Mesh3D를 반환합니다.
간략 결과에는 제거 전·제거된 개수와 금속·유전체 체적[m³]이 들어갑니다.
`include_mesh=True`는 배열을, 결과의 `include_fields=True`는1V 전위까지 포함합니다.
데이터클래스 직접 생성은 팩토리 검증을 대신하지 않습니다. 결과 식별·형태·유한한
양의 C/에너지·음의 접지 전하·지정 전위와 기존1e-8 원시 장 기준을 유지합니다.
버전 있는 입력은 [별도 저장 어댑터](thick_grid_strip_document.md)를 사용합니다.

시험은 완전 접지판·전폭 트레이스의 해석해 C=eps0*eps_substrate*p²M/h 세 조건1e-11,
폭 증가 단조, 전체 길이·유전율 배율1e-10, 분리된 접지 성분, 표면 라벨·체적·재료·
노드 정리, 엄격 입력·예산·복사·원래 실패를 검사합니다. 독립 scikit-fem12.0.2의
네 P1 비교는 같은 정리된 메시에서 좌표 기반 재료 지정·조립·해법을 별도로 사용하며
C·에너지·접지 전하 상대1e-10을 요구합니다. 독립 메시 생성이나 실측 검증은 아닙니다.

p=1mm, g=w=.5p, h=.5p, t=.25p, 기판 유전율3.8·외부1의 별도 수렴 시험에서 마지막
변화는 메시8/16/24 **1.2373%**(<3%), 횡방향 M3/5/7 **0.0568%**(<1%),
상단 .5p/p/2p **0.6738%**(<1%), 하단 .5p/p/2p **0.0000123%**(<0.1%)입니다.
각 변화는 감소합니다. 외곽 시험은 p/8 간격을 유지하고 상하 시험의 M은5입니다.
메시 시험은 M1·상하 여유 p입니다. 참오차 상한이나 통합 개방 경계 한계는 아닙니다.

두께 비교에서는 같은 유한요소 공간을 유지해야 합니다. 초기 연구는 얇은8층 기준과
별도로 재분할한 두꺼운8+2층을 비교하여 네 차이 중 셋이 음수, 최소 -0.01511%로
단조 검사를 실패했습니다. 이 실패는 그대로 보존하며 통과로 바꾸지 않습니다.
각각의 동일 메시에서 금속 두께만 제거해 풀면 양의 금속 효과와 더 큰 음의 메시
기준 변화가 분리됩니다.

조건을 명시한 비교에서는 아래 간격 p/32와 얇은32층 기준을 고정합니다.
t/p=.25,.125,.0625,.03125에 `(cells_below,cells_grid)`를
`(24,8),(28,4),(30,2),(31,1)`로 두고 n8·기판4·상단8을 유지합니다.
상대 차이는0.05638%에서0.02376%로 감소하며1e-10 안에서 음수가 아니고 마지막은1%
미만입니다. 임의 재분할 사이의 단조는 보장하지 않으며 다른 기하와 분할은 별도
평가해야 합니다. 기존 솔버와 수치 허용 기준은 변경하지 않았습니다.

이 유한 영역 정전장 모델은 트레이스 유한 두께·귀환전류 인덕턴스·단위길이 RLGC·
임피던스·도체 손실·전파·방사·실측 정확도를 추론하지 않습니다. 기준 도구는 시험
전용이며 런타임 의존성·웹사이트·실행파일 변경을 포함하지 않습니다.
