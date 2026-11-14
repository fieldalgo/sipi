# 정전용량 형상미분 전류를 쓰는 저장 선로

`ShapePanelTransmissionLineDocument`는 명시 형상미분 전류를
`sipi.shape-panel-transmission-line/1`로 저장합니다. 키는 `schema`, `line`,
`step_fraction` 세 개입니다. 중첩 `line`은 `panel-transmission-line/1` 또는 `/2`로,
기존 패널 제어와 legacy·고정 코팅 선로 계약을 보존합니다. 기존 생성자와 스키마
기본값은 유지하며 일반 panel line이 이 방법으로 자동 전환되지 않습니다.

정규화는 필드를 풀지 않고 전체 중첩 입력과 변형 다각형을 검사합니다.
차분 비율·볼록 유한 두께·하부 접지와 열린 외벽·표면 금속 제한은
[형상미분 전류](panel_shape_conductor.md) 계약을 따릅니다. 공유 솔버의 내부 적분과
영역 제한은 실제 풀이 시 검사하며 다른 방법으로 임의 대체하지 않습니다.

분석은 이 진공 전류 계수와 저장된 체적 메시로 동일 기하의 C/G를 합성합니다.
외부 인덕턴스는 같은 진공 C0를 사용하고, 경계별 금속 법칙이 R과 내부 L을 줍니다.
완전도체의 R·내부 L은 0입니다. 주파수별 전체 네트워크에는 저장 길이와 기준 포트
임피던스를 사용합니다. 고정 코팅의 원래 재료 계약도 유지합니다.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.execution import execute_saved, normalize_saved

section = CrossSection([Layer('uniform', .002, 4.2, tan_delta=.02)],
    [Trace('signal', 0., .0005, .0002, thickness=35e-6)], .004)
metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness={'kind': 'smooth'})
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)), [1e9, 2e9],
    materials={}, conductor=dict(kind='surface-boundaries',
        conductors={'signal': metal}, reference=metal, ground_thickness=35e-6),
    length=.02, schema='sipi.transmission-line/3')
source = ShapePanelTransmissionLineDocument(PanelTransmissionLineDocument(
    line, panels_per_edge=16, ground_modes=512, interpolation_degree=16))
assert normalize_saved(source.dumps()) == source.dumps()
output = execute_saved(source.dumps(), max_evaluations=2)
assert output['status'] == 'complete'
current = output['result']['current_solver']
assert current['kind'] == 'grounded-rectangle-capacitance-shape'
assert len(current['samples']) == 9
```

공통 실행과 `SavedExecutionRequest`는 기존 `characteristic`·`modes` 진단을 지원합니다.
일반 panel line처럼 `max_evaluations`는 **필드 풀이 전 주파수 개수**를 검사합니다.
내부 패널 풀이 횟수나 메모리·시간 제한이 아닙니다. 형상미분 한 번에는
`1+4*(도체 수+1)`회 공유 풀이가 필요합니다. 중단과 자원 제한은 호스트가 담당합니다.

출력의 current solver 기록에는 제어값·C0·순서 있는 경계 계수와 전류·진단값,
reference 합산 전후의 두 차분 행렬, 모든 정확한 요청과 정전용량 표본을 보존합니다.
`ShapePanelLineError`는 재료 검사·도체 검사·전류·메시·유전체·네트워크 단계를 구분합니다.
후속 단계 실패 시 완료된 전류 작업을 남기고, 전류 풀이 실패 시에는 부분 표본과
실패한 요청을 남깁니다. 공통 실행은 `status='failed'`, null 결과, 이 오류 기록을
반환합니다. 사용자 중단은 전파합니다. `SavedExecutionRecord`는 필드 재실행 없이
성공·실패 영수증을 보존합니다. 산출물 선언은 호스트 선언이며 저장만으로 검증되지 않습니다.

실제 legacy·코팅 필드, 직접·공통·영수증 일치, 균질 유전체 항등식, 독립 코팅 전달과
전체 네트워크 행렬, 엄격한 중첩 입력, 각 실패 단계와 중단을 검사합니다.
패널과 유한 외곽 변화 관측은 분리해 보존합니다. 저장 실행이나 차분폭 검사 성공이
요청한 물리 정확도를 보장하지는 않습니다. 이 단위에는 자동 해상도 수락·역산·공차
수율·브라우저 검증·배포를 추가하지 않습니다.

[형상전류 선로 분리 해상도 검사](shape_panel_resolution.md)로 패널·체적·동시 세분과
명시 외곽 비교를 각각 보존할 수 있습니다.
