# 정해진 영역에서 얇은 신호선과 격자 접지의 정전용량

[English](../../../../../packages/sipi/strip_grid.md) | **한국어**

`strip_grid_cell`은 정합 사면체 셀을 만들고 `extract_strip_grid_capacitance`는
공유 [3D 정전용량 추출기](capacitance3d.md)로 **전체 정전용량 C[F]**를 풉니다.
`StripGridCell`·`StripGridCapacitance`는 기하·유전체·장 결과를 보존합니다.
[넓은 평판 기준 셀](grid_plate.md)을 유한 폭의 얇은 신호선과 세 유전체 영역으로
확장합니다. 단위길이 RLGC·특성 임피던스·귀환 전류 인덕턴스·전파·방사를 추론하지 않습니다.

```python
from sipi import strip_grid_cell

inputs = dict(pitch=1e-3, grid_width=.5e-3, trace_width=.5e-3,
              height=.5e-3, top_clearance=1e-3, backside_depth=1e-3,
              eps_substrate=3.8, eps_above=1., eps_below=1.,
              transverse_periods=3, cells_per_pitch=4,
              cells_substrate=2, cells_above=4, cells_below=4)
cell = strip_grid_cell(**inputs)
mesh = cell.to_mesh()  # detached shared Mesh3D; electrode node sets stay explicit
assert cell.relative_permittivity.shape == (len(cell.tets),)
```

x 길이는 한 피치 p이고 y는0부터 M*p까지 홀수 M개의 피치를 포함합니다.
z=0의 0두께 격자는 정수 피치 x/y 선을 중심으로 폭 g인 접지 띠가 교차합니다.
z=h의 0두께 신호선은 전체 x를 가로지르며 y=M*p/2를 중심으로 폭 w를 가집니다.
신호선은1V, 격자는0V입니다. 유전체는 아래 z=-backside_depth부터 위 h+top_clearance까지
있고, z<0은 eps_below, 0..h는 eps_substrate, h 위는 eps_above입니다.
경계면은 메시와 정확히 정합합니다.

지정하지 않은 외곽은 모두 절연 경계입니다. x 끝은 격자 중심의 반사 대칭면이며
횡방향 양옆·위·아래는 사용자가 고른 유한 경계입니다. 자동 개방 공간이나 주기
파동 포트가 아닙니다. 횡방향 크기와 위·아래 여유는 메시 크기와 각각 따로
검토해야 합니다. 유한 도체 두께·기울어진 선로·중심에서 벗어난 선로·변하는 피치는
추론하지 않으며 계산 성공이 전체 인터커넥트 모델이나 실측 검증을 뜻하지 않습니다.

```python
from sipi import extract_strip_grid_capacitance

result = extract_strip_grid_capacitance(**inputs)
assert result.capacitance_f > 0
compact = result.to_dict()
assert compact['stored_energy_j_at_one_volt'] == .5*result.field.energy_C[0, 0]
assert not compact['fields_included']
expanded = result.to_dict(include_fields=True)
assert len(expanded['potential_v_at_one_volt']) == len(result.cell.nodes)
```

14개 입력을 모두 명시해야 합니다. 길이·상대 유전율은 불리언을 제외한 유한한 양의
실수 스칼라입니다. grid_width<=pitch, trace_width<=M*pitch여야 합니다.
M은1..9의 홀수 정수, cells_per_pitch는4..32의 짝수 정수입니다. 세 수직 영역은 각각
1..128의 독립적인 정수 셀 수를 가집니다. 위 경계 좌표는 유한하고 부동소수점에서도
h보다 커야 합니다. 두 반폭은 상대1e-12 반올림 차이 이내에서 횡방향 메시와 맞아야
합니다. 형상 근사로 반올림하지 않고 비정합 입력을 거부하며 요청 폭·실제 폭을 함께 보존합니다.

메시 생성 전에 노드100000·사면체500000 이하와 유한 양의 상자 체적을 검사합니다.
실제 사면체 체적도 유한 양수이며 합은 상자 체적과 상대1e-12 이내로 같아야 합니다.
전극 평면과 유전체 배치를 보존합니다. 자원 제한은 정확도 기준이 아니며 극단적인 작은
기하는 장 조립·풀이 단계에서 실패할 수 있습니다.

`cell.inputs`는14키 SI 입력의 새 사본입니다. 노드·사면체·신호/접지 노드 집합과
`relative_permittivity`는 복사한 읽기 전용입니다. `to_mesh()`는 별도 공유 Mesh3D
사본을 주며 face tag를 추론하지 않습니다. 다른 솔버에는 전극 집합과 사면체별 유전율을
함께 전달해야 합니다. `to_dict()`의 기본값은 간결하며 `include_mesh=True`로 배열을
포함합니다. 자료형을 직접 구성하는 것은 factory 검증을 대신하지 않습니다.

결과는 `capacitance_f`, 원래의 에너지·전하·Maxwell 진단과 `Capacitance3D` 장을 제공합니다.
직렬화의 에너지 정전용량은 F,1V에서 저장 에너지는 그 절반인 J, 접지 전하는 C입니다.
`include_fields=True`는 메시·재료·1V 전위를 포함합니다. 기본 결과는 간결하며 버전 있는 저장 입력은
[별도 adapter](strip_grid_document.md)를 사용합니다. 원래1e-8 장 기준을 유지하며 결과 자료형·
크기·유한 양의 C/에너지·음의 접지 전하·지정 전위를 검사합니다.

`tests/sipi/test_strip_grid.py`는 solid/full-width 평행판3조건
C=eps0*eps_substrate*p*(M*p)/h를 상대1e-11, 격자/신호 폭 증가의 단조성,
전체 길이·세 영역 유전율의 배율을1e-10으로 검사합니다. 독립 scikit-fem12.0.2
P1 weak form4조건은 같은 명시 메시에서 좌표 기반 재료 배치와 별도 조립·풀이를
사용하며 C·에너지·접지 전하의 상대 차이는1e-10 이하여야 합니다. 메셔 독립 대조는
아닙니다. 균일 유전체·전체 폭 신호선과 기존 넓은 평판 API의 일치는 별도 재현 근거입니다.

p=1mm, g=w=.5p, h=.5p, 기판 eps3.8·외부 eps1에서 등록한 연속 변화 기준은 다음과 같습니다.

| 변경 | 고정 조건 | pilot의 마지막 변화 | 수락 기준 |
|---|---|---|---|
| 피치당 메시8/16/24 | M1, 위·아래 p, 수직 간격 p/n |1.2840%|감소하며3% 미만|
| 횡방향 M3/5/7 | n8, 위·아래 p |0.0569%|감소하며1% 미만|
| 위 여유 .5p/p/2p | n8, M5, 아래 p, 간격 고정 |0.6739%|감소하며1% 미만|
| 아래 여유 .5p/p/2p | n8, M5, 위 p, 간격 고정 |0.000393%|감소하며0.1% 미만|

각각의 연속 변화이며 참오차 상한이나 결합된 개방 경계 극한이 아닙니다. 다른 기하·재료와
결합 세분은 다시 확인해야 합니다. 엄격 입력·사전 자원 제한·층별 체적·전극 라벨·읽기 전용
복사·결과 훼손·원래 솔버 실패도 검사합니다. BSD-3-Clause 기준 도구는 시험 전용으로
유지하며 새 의존성을 추가하지 않습니다.
