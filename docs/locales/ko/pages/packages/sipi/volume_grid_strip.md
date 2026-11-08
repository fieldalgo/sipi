# 유한 두께 신호선·접지 격자 체적

[English](../../../../../packages/sipi/volume_grid_strip.md) | **한국어**

`volume_grid_strip_cell`과 `extract_volume_grid_strip_capacitance`는 직사각형
신호선과 사각 접지 격자라는 두 유한 PEC 체적을 갖는 정전장 셀을 준비·계산합니다.
`VolumeGridStripCell`과 `VolumeGridStripCapacitance`는 기하·재료와 **전체 C[F]**를
보존합니다. [두꺼운 접지 위의 얇은 신호선](thick_grid_strip.md)은 별도 API로 유지합니다.

```python
from sipi import volume_grid_strip_cell

inputs = dict(pitch=1e-3, grid_width=.5e-3, trace_width=.5e-3,
              height=.5e-3, top_clearance=1e-3, backside_depth=1e-3,
              ground_thickness=.25e-3, trace_thickness=.25e-3,
              eps_substrate=3.8, eps_above=1., eps_below=1.,
              transverse_periods=3, cells_per_pitch=4, cells_substrate=2,
              cells_above=4, cells_below=3, cells_grid=1, cells_trace=1)
cell = volume_grid_strip_cell(**inputs)
assert cell.ground_metal_volume > 0 and cell.trace_metal_volume > 0
assert cell.relative_permittivity.shape == (len(cell.tets),)
```

x 길이는 피치 p, y 폭은 홀수 M개 피치입니다. 폭 g인 접지 띠는 정수 피치 x/y
선에서 교차하며 -tg..0을 차지하고0V입니다. 중앙의 폭 w인 신호선은 x 전체를 지나
h..h+ts를 차지하고1V입니다. **높이 h는 유전체 간격**이며 위 경계는
h+ts+top_clearance, 아래는 -backside_depth입니다. 금속을 제외한 z<0,0..h,h 위에
각각 명시한 양의 실수 상대 유전율을 적용합니다. 나머지 면은 절연·반사 경계이며
유한 외곽을 자동 개방 공간이나 파동 포트로 해석하지 않습니다.

18개 입력 모두 필수입니다. 치수·유전율은 불리언을 제외한 유한 양의 실수이며
0<tg<backside_depth, g<=p, w<=M*p, 홀수 M1..9, 짝수 피치 셀4..32를 요구합니다.
두 반폭은 상대1e-12 반올림 범위에서 정합하고 요청 폭과 실제 폭을 따로 보존합니다.
수직 정수 셀 수1..128 다섯 개를 명시합니다. `cells_below`는 -d..-tg,
`cells_grid`는 -tg..0, `cells_substrate`는0..h, `cells_trace`는 h..h+ts,
`cells_above`는 h+ts..h+ts+a입니다. 신호선 윗면은 유한하고 h보다 커야 하며
그 위 여유도 양수로 표현 가능해야 합니다.

할당 전 금속 제거 전 노드100000·사면체500000 예산과 유한 양의 상자 체적을
검사합니다. 두 PEC 체적을 제거하고 미사용 노드 삭제·인덱스 재지정을 합니다.
금속을 가상 유전체로 대체하지 않습니다. 양의 사면체 체적 합은 상자에서 두 금속을
뺀 값과 상대1e-12 안에서 맞아야 합니다. 전극 표면과 세 재료 영역은 명시적입니다.
전체 접지판·전폭 신호선은 유전체를 세 성분으로 나누며 위 영역은 신호선만 접하고
일정한1V입니다. [분리 영역 추출기](partitioned_capacitance.md)는 각 영역의 지정
전극과 전체 전극 관계의 접지 기준을 검사합니다.

```python
from sipi import extract_volume_grid_strip_capacitance

result = extract_volume_grid_strip_capacitance(**inputs)
assert result.capacitance_f > 0
compact = result.to_dict()
assert compact['stored_energy_j_at_one_volt'] == .5*result.field.energy_C[0, 0]
assert not compact['fields_included']
expanded = result.to_dict(include_fields=True)
assert len(expanded['potential_v_at_one_volt']) == len(result.cell.nodes)
```

입력은 독립18키 스냅샷입니다. 기하·노드 집합·사면체별 재료는 복사된 읽기 전용
배열입니다. `to_mesh()`는 면 태그를 추론하지 않는 독립 Mesh3D를 반환합니다.
간략 직렬화에는 제거 전·제거된 개수, 별도 `ground_metal_volume_m3`와
`trace_metal_volume_m3`, 유전체 체적, 실제 폭·edge index가 들어갑니다.
`include_mesh=True`는 배열을, 결과의 `include_fields=True`는1V 전위를 추가합니다.
데이터클래스 직접 생성은 팩토리 검증을 대신하지 않습니다. 원시 장1e-8 기준과
결과 식별·형태·유한 양의 C/에너지·음의 접지 전하·지정 전위를 검사합니다.
버전 있는 입력은 [별도 저장 어댑터](volume_grid_strip_document.md)를 사용합니다.

검증은 세 완전 접지판·전폭 해석 C=eps0*eps_substrate*p²M/h의1e-11, 위아래
상수 전위1e-10, 폭 증가 단조, 길이·전체 유전율 배율1e-10, 두 금속 체적·재료
분할·전극 표면·노드 정리·분리 성분·엄격 입력/자원·복사·원래 오류를 포함합니다.
독립 scikit-fem12.0.2의 네 P1 약형은 같은 정리된 메시에서 좌표 기반 재료·조립·
해법을 별도로 사용해 C·에너지·접지 전하1e-10을 검사합니다. 독립 메시 비교는 아닙니다.

p=1mm,g=w=.5p,h=.5p,tg=ts=.25p,기판3.8·외부1의 별도 수렴에서 마지막 변화는
메시8/16/24 **1.0299%**(<3%), 횡방향 M3/5/7 **0.1806%**(<1%), 위 여유
.5p/p/2p **0.6933%**(<1%), 아래 여유 .5p/p/2p **0.00001154%**(<0.1%)입니다.
각 변화가 감소합니다. 메시 시험은 M1·상하 p, 외곽 시험은 p/8 간격을 고정하고
상하 시험은 M5입니다. 참오차 상한이나 통합 개방 경계 극한은 아닙니다.

얇은 신호선 비교는 절대 위 경계 h+p와 위 간격 p/128을 고정합니다.
n8·기판4·아래6·격자2이고 얇은 신호선 기준은 위128층입니다.
ts/p=1/16,1/32,1/64,1/128에서 신호선 셀8/4/2/1, 위 셀120/124/126/127을 사용하며
top_clearance=p-ts입니다. C/Cthin-1은0.31088%에서0.05165%로 감소하고1e-10 안에서
음수가 아니며 마지막은1% 미만입니다. 절대 위 경계와 같은 유한요소 공간을 유지하여
두께와 외곽·재분할 효과를 분리합니다. 임의 재분할 단조는 보장하지 않으며 다른
기하는 별도 평가가 필요합니다.

직사각형 완전도체 정전장 모델이며 유한 전도도·거칠기·귀환 인덕턴스·선로 RLGC·
임피던스·전파·방사·실측 정확도를 추론하지 않습니다. 기존 API·스키마·공유 솔버는
변경하지 않으며 새 의존성·앱·플랫폼 지원을 추가하지 않습니다.
