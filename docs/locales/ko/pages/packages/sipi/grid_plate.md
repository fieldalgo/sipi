# 유한 영역의 얇은 격자 접지와 넓은 판 정전용량

`grid_plate_cell`은 장 계산 없이 정합된 정전장 기준 셀을 만들고,
`extract_grid_plate_capacitance`는 같은 명시 입력으로 기존
[유한 영역 3D P1 추출기](capacitance3d.md)를 사용하여 **F 단위 전체 정전용량**을
반환합니다. 넓은 PEC 판 아래 정사각 얇은 접지 격자이며 선로 또는 귀환 전류
모델이 아닙니다.

균일 유전체가 pitch×pitch 셀을 채웁니다. z=0의 두께0 접지판은 셀의
네 측면 경계를 중심으로 놓인 폭 `width`의 교차 띠의 합집합입니다.
상부 전체 면 z=`height`에1V를 주고 아래 z=−`backside_depth` 및 측면은
절연(법선 전속0) 경계입니다. 측면 반사 대칭은 균일한 넓은 판과 대칭
격자를 전제로 합니다. 유한 아래 경계를 자동 개방 경계로 취급하지 않으며
뒤쪽 깊이 수렴을 별도로 확인해야 합니다.

8개 입력을 모두 명시합니다. `pitch`, `width`, `height`, `backside_depth`는
유한 양수 m, `width<=pitch`, `eps_r`는 유한 양수 실수 상수입니다.
`cells_xy`는 짝수 정수4..64, `cells_above`는 정수1..64,
`cells_below`는 정수1..128이며 상하 분할을 각각 지정합니다.
반 띠 폭은 횡방향 셀 간격의 정수 배수에 상대1e-12 반올림 범위 내에서
맞아야 합니다. 격자에 맞지 않는 폭은 거부하고 요청 폭과 실제 정합 폭을
둘 다 보존합니다. 이는 기하 정확도 허용치가 아닌 반올림 정합 규칙이며
입력이나 세분 수를 추론하지 않습니다.

메시 생성 전에100000개 노드·500000개 사면체 상한 및 표현 가능한 양의
전체 체적을 검사합니다. 공유 `galerkin.box_mesh` 연결을 상하 두 z 구간에
좌표 변환하며 별도 솔버/메셔를 만들지 않습니다. 지정 평면을 정확히
유지하고 모든 사면체 체적은 유한 양수, 전체 체적은
pitch²*(height+backside_depth)와 상대1e-12 이내로 일치해야 합니다.
상한은 정확도나 실행 시간 보증이 아닙니다.

```python
from sipi import grid_plate_cell, extract_grid_plate_capacitance

inputs = dict(pitch=1e-3, width=.25e-3, height=.5e-3, backside_depth=1e-3,
    eps_r=3.8, cells_xy=8, cells_above=4, cells_below=8)
cell = grid_plate_cell(**inputs)
assert cell.resolved_width == inputs['width']
assert cell.nodes.shape == (1053, 3)
assert cell.tets.shape == (4608, 4)
assert cell.to_dict()['input']['width_m'] == inputs['width']
```

```python
result = extract_grid_plate_capacitance(**inputs)
assert 0 < result.capacitance_f < 6.73e-14
summary = result.to_dict()
assert not summary['fields_included']
assert summary['stored_energy_j_at_one_volt'] > 0
assert summary['ground_charge_c_at_one_volt'] < 0
field = result.to_dict(include_fields=True)
assert len(field['potential_v_at_one_volt']) == len(result.cell.nodes)
```

`GridPlateCell`의 노드·사면체·전극 배열은 복사 후 읽기 전용이며 `inputs`는
매번 새 SI 입력 사본입니다. `to_mesh()`는 외부 태그가 없는 공유 `Mesh3D`
사본을 만들므로 추출기에 전달할 때 명시 `plate_nodes`와 `ground_nodes`를
사용합니다. 기본 기하 결과는 간결하며 `to_dict(include_mesh=True)`에서
메시를 포함합니다.

`GridPlateCapacitance.cell`은 기하를, `.field`는 원래 `Capacitance3D`를
보존합니다. 판1V·접지0V로 계산하고 원 에너지/전하/Maxwell 기준1e-8을
유지합니다. 정확한 결과 자료형·전극 이름·사면체 수·모든 장 배열 모양·
유한 진단량·지정 전위를 검사합니다. 음의 접지 전하를 보존하며
`capacitance_f`는 셀의 단일 Maxwell 계수입니다. 1V 저장 에너지는
energy capacitance의 절반이고 C 전체를 J로 해석하지 않습니다.
`to_dict(include_fields=True)`에서 메시와 전위 표본을 포함합니다.
이 결과 직렬화는 저장 입력 스키마가 아닙니다.

solid판 해석 eps0*eps_r*pitch²/height 상대1e-11, 폭 증가 시 C 단조 증가와
solid 상한, 길이·유전율 배율1e-10 및 별도 scikit-fem12.0.2 P1 약형과
대조합니다. 독립 약형은 **동일한 명시 메시**의 판 전하·접지 전하·에너지를
1e-10으로 대조하므로 별도 조립·풀이 근거이며 독립 메시 생성 근거가 아닙니다.

pitch1mm/width.25mm/height.5mm/eps3.8의 고정 입력에서 횡방향8/16/32
세분(상하도 같은 간격 유지)에 따른 연속 C 변화가 약1.93%→1.07%로
감소하고 최종1.5% 미만입니다. 실제 오차 상한은 아닙니다. 동일 간격에서
뒤쪽 깊이를1피치에서2피치로 늘렸을 때 C 상대 변화는1e-3 미만입니다.
상하 간격이 다른 경우를 포함한 추가3종 기하도 독립 약형과 대조합니다.
엄격 수치/개수/정합/예산/복사/결과 동일성/원래 실패를 함께 검사하며
사용 입력마다 수렴을 확인해야 합니다.

유한 trace/sheet 두께, 실제 신호선, 귀환 전류 L, RLGC, 손실, 파동 포트,
방사, 주파수 유효범위, 일반 flex 기하와 실측 정확도는 지원 범위 밖입니다.
정전장 셀 C를 검증된 격자 귀환 선로 모델로 대체해서는 안 됩니다.
