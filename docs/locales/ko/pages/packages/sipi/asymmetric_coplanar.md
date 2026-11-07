# 유한 coplanar 접지선 사이의 비대칭 쌍

`asymmetric_coupled_grounded_coplanar`는 아래 접지면 위에 서로 다른 두 표면
신호선과 유한한 직사각형 접지선 두 개를 놓습니다. 왼쪽이 positive, 오른쪽이
negative이며 중앙 접지선은 없습니다. 네 도체 바닥은 모두 `substrate_height`에
있고 유한 상자의 위·옆 경계는 절연입니다.

길이는 미터입니다. 신호선의 `left_width`, `right_width`, `left_thickness`,
`right_thickness`, `left_top_width`, `right_top_width`는 독립입니다. 두께 기본값은
0, 윗폭 기본값은 바닥 폭입니다. 양쪽 접지선은 양의 `ground_width`,
`ground_gap`과 명시적 `ground_thickness`(기본 0)를 공유합니다. 접지 두께는
신호 두께에서 **추론하지 않습니다**. 접지는 직사각형이고 신호선만 사다리꼴입니다.

`gap`은 두 신호 바닥 폭 사이, `ground_gap`은 각 신호 바깥 바닥 끝과 인접 접지
사이의 수평 간격입니다. 신호 전체 바닥 구간의 중심은 0입니다.

```
S = left_width + right_width + gap
x_left = -(gap + right_width)/2
x_right = (gap + left_width)/2
x_ground = +/-(S/2 + ground_gap + ground_width/2)
```

사다리꼴은 실제 면 간격을 줄일 수 있으며 접촉·겹침·상자 잘림·공기 여유 검사를
유지합니다. `eps_r`, `tan_delta`는 기판 물성이고 공기는 유전율 1·손실 0입니다.
기본 공기 두께는 `10*substrate_height+max(left_thickness,right_thickness,
ground_thickness)`, 기본 상자 폭은 `max(20*substrate_height,
4*max(left_width,right_width),S+2*ground_gap+2*ground_width+4*substrate_height)`입니다.
유한 접지 폭은 물리 기하의 일부입니다. 무한 접지로 간주하지 말고 수치 상자 폭·공기
높이와 별도로 영향을 확인하세요.

두 신호가 같고 접지 두께도 같으면 `coupled_grounded_coplanar` 정규 기하와
일치합니다. 비대칭 쌍의 저장 공차·역산에는 `z_diff_forward`가 필요합니다.
이는 공통 발사 전류 0인 전방 차동 전류 기준이며 대칭 홀 모드나 종단 입력
임피던스를 뜻하지 않습니다. 유손실 쌍 line study/2는 별도의 명시적
`differential_forward_impedance_real`과 전체 결합 행렬을 사용합니다.

## 저장 입력과 공차

[두 폭 고정 피치 규칙](asymmetric_pitch.md)은
`gap=fixed_pitch_m-(left_width+right_width)/2`를 유도합니다. 접지선은 지정한
접지 간격을 유지하도록 전체 신호 구간과 함께 움직이므로 절대 위치 고정이 아닙니다.
접지 간격·폭·두께는 명시적 표본 변수입니다. nominal도 피치를 만족해야 하고
피치 제약 아래 gap을 따로 샘플링할 수 없습니다. 전체 접지면 간격 고정 제약은
이 구조에 적용하지 않습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    left_thickness=35e-6, right_thickness=50e-6,
    ground_width=1.5e-3, ground_gap=.25e-3, ground_thickness=35e-6,
    box_width=12e-3, air_height=5e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_grounded_coplanar', parameters,
    quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    sampling=dict(kind='uniform', count=2, seed=71,
        variables=[dict(name='left_width', lower=.28e-3, upper=.32e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze(max_evaluations=2)
assert result.failed == 0 and len(result.rows) == 2
for row in result.rows:
    a, b, left_ground, right_ground = row.document.section.traces
    assert abs(b.x-a.x-.7e-3) < 1e-15
    assert abs(a.x0-left_ground.x1-.25e-3) < 1e-15
```

sweep·corners·uniform·상관 normal 규칙을 유지합니다. 유계 입력의 잘못된 기하는
해석 전에 거부하고, 잘못된 정규 표본은 잘라내거나 재추출하지 않고 실패 행으로
보존합니다. 재료 study/3·/4는 `substrate` 영역에 연결합니다. 기존 iid 수율,
폭 역산과 유손실 쌍 공차가 입력을 재사용합니다. 템플릿 33종·저장 스키마 42종이며
필드나 실행 의존성을 추가하지 않습니다. 이전 판독기는 새 이름을 거부할 수 있으므로
정확한 엔진·휠을 입력과 함께 기록하세요.

## 독립 수락 기준

위 유한 동박 fixture는 메시 `(edge_size,far_size,grade)`
`(5 um,.25 mm,.2)`→`(2.5 um,.125 mm,.1)`의 C/전방 Z 차이를 1.5% 이내로
요구합니다. 세밀한 메시에서 상자 폭 12→24 mm, 공기 높이 5→10 mm를 각각 따로
바꾼 차이는 .5% 이내입니다. 접지 폭 1.5→3 mm의 물리 기하 변화에는 별도 1%
민감도 기준을 둡니다. 임의 입력의 외곽 수렴이나 접지 폭 무관성을 보장하지 않습니다.

scikit-fem 12.0.2(BSD-3-Clause)의 독립 복소/진공 P1 에너지 조립으로 같은
메시의 C/C_loss/C0를 normwise 상대 `1e-10`에 대조합니다. 별도로 계수 배율과
진공 항등식 `1e-12`, 상반성·수동성과 반사한 도체 순열 .5% 이내를 확인합니다.

두 번째 독립 기준은 해석적 이미지 전하 Green 적분·상수 전하 패널·조밀 행렬 풀이로,
SIPI 기하·메시·솔버를 사용하지 않습니다. 모든 두께 0·진공에서 신호 구간
[-.55,-.25], [.05,.55] mm, 접지 구간 [-2.3,-.8], [.8,2.3] mm, 높이 .5 mm입니다.
접지를 0 V로 둔 신호 C 부분행렬에서 `Zc=inv(C)/c`를 구합니다. 도체당 80→160
패널 기준 차이는 .3% 미만, 세밀한 FEM C/Z 오차는 2% 미만이며 거친 메시보다
감소해야 합니다. 상자·공기를 함께 두 배로 바꾼 차이는 1% 미만입니다. 이 얇은
진공 한계는 유한 동박·기판 물성 검증을 대체하지 않습니다.

고정 피치 .7 mm·왼쪽 폭 [.1,.8] mm의 100 ohm 역산은 요청/세분/상자 확대/
공기 확대 잔차가 각 1 ohm 이내, 외곽 Z 변화가 각 .5% 미만이어야 합니다.
재료·수율·유손실 직접 재현은 `1e-10`을 사용합니다. 수치 fixture 검사이며 실측
보드 정확도·일반 3D 구조나 앱·플랫폼 수락을 뜻하지 않습니다.

[공차](study.md) · [English](../../../../../packages/sipi/asymmetric_coplanar.md)
