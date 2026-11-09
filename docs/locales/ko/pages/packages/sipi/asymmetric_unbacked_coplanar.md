# 뒷면 접지판이 없는 비대칭 coplanar 쌍

[평면 코팅 비대칭 쌍](asymmetric_coated_unbacked_coplanar.md)은 기판 위에 명시적인 전체 폭 코팅을 추가합니다.

`asymmetric_coupled_unbacked_coplanar`는 유한 기판 위의 유한 coplanar 접지 사이에
서로 다른 두 신호를 둡니다. **뒷면 접지판이 없습니다.** 아래·위 공기층과 절연 외곽을
사용하며 두 접지 trace만 공통 기준을 정의합니다. 균일 2D 단면이고 중앙 접지나
교환 대칭을 가정하지 않습니다.

신호 폭·두께·선택적 윗폭은 독립적입니다. 직사각형 접지는 명시적
`ground_width`, `ground_gap`, `ground_thickness`(기본 0)를 공유하며 신호 두께를
따라가지 않습니다. 신호 아랫면 전체 폭은 중앙에 놓이고 positive는 왼쪽,
negative는 오른쪽입니다. `gap`과 `ground_gap`은 아랫변 간격이며 테이퍼 접촉·
외곽 잘림 검사를 유지합니다. 길이는 모두 m입니다.

영역은 `lower_air`, `substrate`, `air`이며 기판은 별도 `eps_r`·`tan_delta`를
가집니다. 금속 아랫면은 `lower_air_height+substrate_height`에 있습니다.
상부 `air_height`는 기판 윗면에서 시작해 **금속 높이를 포함**하며 모든 금속보다
높아야 합니다. 하부 공기는 양수이며 기본값은 기판 높이의 10배입니다.
자동 상부 공기는 기판 높이 10배에 가장 큰 금속 두께를 더합니다.
명시적 공기·상자 크기는 공차 분석 중 기본값의 의존성을 피합니다.
접지 폭은 물리 입력이며 상자·양쪽 공기 높이는 별도 외곽 절단입니다.
접지를 넓히는 것을 외곽 수렴으로 간주하지 않습니다.

신호 치수와 접지 두께를 같게 두면 자동 상자 크기를 포함해
`coupled_unbacked_coplanar`로 환원합니다. 기존 저장 공차·역산에 새 템플릿 이름을
등록하며 새 스키마는 없습니다. 이전 reader는 새 이름을 거부할 수 있습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    left_thickness=35e-6, right_thickness=50e-6,
    ground_gap=.25e-3, ground_width=1.5e-3, ground_thickness=35e-6,
    box_width=12e-3, air_height=6e-3, lower_air_height=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_unbacked_coplanar', parameters,
    quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    sampling=dict(kind='uniform', count=2, seed=71, variables=[
        dict(name='left_width', lower=.28e-3, upper=.32e-3),
        dict(name='ground_gap', lower=.24e-3, upper=.26e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze(max_evaluations=2)
assert result.failed == 0
for row in result.rows:
    p = row.parameters
    assert abs(p['gap']+(p['left_width']+p['right_width'])/2-.7e-3) < 1e-15
    assert row.document.section.bottom == 'open'
    assert row.document.section.traces[0].y == p['lower_air_height']+p['substrate_height']
```

전방량 `z_diff_forward`는 공통 전류를 0으로 두며 홀수 고유모드나 종단 임피던스가
아닙니다. 고정 피치는 `gap=pitch-(left_width+right_width)/2`로 간격을 정하고
접지는 바깥 신호와의 간격을 유지하며 이동합니다. 잘못된 유한 경계 기하는 메시 전에
거부하고 잘못된 정규 표본은 재추출·잘림 없이 실패로 보존합니다.
기판 재료 study/4·iid 수율·유손실 쌍 line-study/2도 같은 기하를 사용합니다.
유손실 공차는 실수 정전 전방량과 구분되는
`differential_forward_impedance_real`을 명시적으로 선택합니다.

## 독립 수락 계약

위 유한 금속 사례의 edge/far/grade `(5um,.25mm,.2)`→`(2.5um,.125mm,.1)`
C/Z 변화는 <1.5%입니다. 세밀한 메시에서 상자 12→24mm, 위 공기 6→12mm,
아래 공기 6→12mm 각각 <.5%를 요구합니다. 접지 폭 1.5→3mm는 물리 민감도로
별도 기록하며 그 효과를 수치 오차라고 주장하지 않습니다.
독립 scikit-fem 12.0.2(BSD-3-Clause)의 같은 메시 복소/진공 P1 에너지는
C/C_loss/C0에 정규화 1e-10을 요구합니다. 독립 기하·메시 생성 검사는 아닙니다.
일괄 계수 배율·공통 손실·진공 L·상호성은 1e-12, 좌우 반사와 신호 순서 치환은 .5%입니다.

별도의 두께 0·전체 진공 사례는 총 전하 0과 미지 공통 전위를 둔 독립 자유공간
`-log(distance)` 패널 Green 적분을 사용합니다. 이미지 접지면을 더하거나 먼 경계를
접지하지 않습니다. 명시 신호 구간 [-.55,-.25], [.05,.55]mm와 접지 구간
[-2.3,-.8], [.8,2.3]mm는 factory와 독립입니다.
80→160패널 C/Z 변화는 <.3%, 상자 24mm·양쪽 공기 12mm의
FEM `(4um,.5mm,.2)`→`(1um,.25mm,.1)` 오차는 감소하고 최종 <2%여야 합니다.
상자 48mm·양쪽 공기 24mm의 C/Z 변화는 <1%입니다. 기존 독립 패널 검사는
전하 중성·게이지·상호성·척도 불변성과 대칭 유한 접지의 타원적분 극한도 확인합니다.

고정 피치 .7mm의 왼쪽 폭 목표는 [.08,.85]mm 범위, 100Ω·허용 1Ω·최대 30평가입니다.
요청한 세밀한 메시·자동 절반 세분·확대한 상자/위 공기/아래 공기에서 같은 폭이
목표 허용범위를 만족해야 합니다. 재료·전체 복소 선로 재실행은 1e-10입니다.
이 명시 사례 기준은 실측 기판·일반 3D·브라우저·Windows 정확도 수락이 아닙니다.

[공차](study.md) · [English](../../../../../packages/sipi/asymmetric_unbacked_coplanar.md)
