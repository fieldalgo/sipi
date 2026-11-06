# 좌우가 다른 표면 선로 쌍과 전방 전류 임피던스

asymmetric_coupled_microstrip은 공통 접지 기판 위 두 선로에 서로 다른 밑면 폭·두께·
윗면 폭을 지정합니다. 왼쪽은 positive, 오른쪽은 negative이며 둘 다 substrate_height에서
시작합니다. gap은 밑면 가장자리 사이 거리이고 전체 밑면 폭 범위의 중심은 x=0입니다.

필수 인자는 left_width·right_width·gap·substrate_height·eps_r입니다.
left_thickness/right_thickness 기본값은 0, left_top_width/right_top_width는 None
(직사각형), tan_delta는 0입니다. 길이는 미터입니다. 기존 Trace 계약에 따라 중심이
맞는 사다리꼴을 지원하며 겹치거나 영역 밖으로 나가지 않으면 더 넓은 윗면도 허용합니다.
두께는 비음수, 폭·간격·높이·eps_r는 양의 유한값입니다. 기존 기하 검사로 겹침·잘못된
테이퍼·영역 잘림을 거부합니다.

기판 표면부터의 기본 공기 높이는 10*substrate_height+max(두께)입니다.
기본 상자 폭은 max(20*substrate_height,4*span), span=left_width+gap+right_width입니다.
수렴 확인을 위해 둘 다 명시할 수 있습니다. 좌우가 같으면 기존 coupled_microstrip의
기하와 JSON byte가 같습니다. 직사각형은 기존 v1, 테이퍼는 기존 v2 기하를 사용합니다.

## 명시적인 실수 전방 전류 목표

LineParameters.characteristic_impedance_matrix()는 Zc C Zc=L을 만족하는 실수 양의
정부호 Zc를 반환합니다. C는 Re(C_complex), L은 진공 C0에서 구한 외부 인덕턴스입니다.
검증된 무손실 RLGC 행렬 솔버를 기준 1 Hz에서 사용하며 R=G=0에서는 이 임의 주파수가
상쇄됩니다. 결과는 읽기 전용 사본이고 추가 장 해석이 없습니다.

두 신호에서 line.z_diff_forward=dᵀZc d, d=[1,-1]입니다. **Icommon=0인 전방
입력**, 즉 I=[Idiff,-Idiff]에서 Vdiff/Idiff입니다. 비대칭 쌍에서는 공통 전압도
생기고 전파 중 성분이 섞일 수 있으므로 독립 차동 고유모드는 아닙니다. 대칭 극한에서
2*Zodd로 환원됩니다. 기존 even_odd()/z_diff 대칭 관문은 그대로입니다. 복소 주파수
RLGC 응답에는 [전체 혼합 특성 행렬](mixed_characteristic.md)을 사용하세요.

이 진단은 도체 R과 명시적인 유전체 G/C_loss를 제외합니다. 손실 재료는 여전히 정전계와
Re(C_complex)에 영향을 줄 수 있습니다. 복소 손실 임피던스·DC 도통 저항·감쇠·대역
목표가 아닙니다. 비물리 행렬·해결되지 않는 조건수·표현 불가능한 출력은 기존 행렬
유효성 검사에서 실패합니다.

## 공차·역산 저장

```python
from sipi import asymmetric_coupled_microstrip, ImpedanceDesignDocument
from sipi.study import ImpedanceStudyDocument

parameters = dict(left_width=.4e-3, right_width=.65e-3, gap=.25e-3,
    substrate_height=.5e-3, eps_r=4, left_thickness=35e-6, right_thickness=50e-6,
    left_top_width=.32e-3, right_top_width=.55e-3, tan_delta=.02,
    air_height=6e-3, box_width=12e-3)
mesh = dict(edge_size=4e-6, far_size=.25e-3, grade=.2)
study = ImpedanceStudyDocument('asymmetric_coupled_microstrip', parameters,
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='left_width', lower=.35e-3, upper=.5e-3)]),
    quantity='z_diff_forward', mesh=mesh)
saved = study.dumps()
rows = ImpedanceStudyDocument.loads(saved).analyze(max_evaluations=3)
assert all(row.complete for row in rows.rows)
goal = ImpedanceDesignDocument('asymmetric_coupled_microstrip', parameters,
    variable='left_width', bounds=[.3e-3, 1.2e-3], target=100,
    quantity='z_diff_forward', tolerance=1,
    mesh=dict(edge_size=2e-6, far_size=.125e-3, grade=.1))
result = ImpedanceDesignDocument.loads(goal.dumps()).solve()
assert abs(result.residual) <= 1 and abs(result.refined_residual) <= 1
```

새 템플릿은 quantity='z_diff_forward'만 받습니다. 기존 모든 쌍 템플릿도 이 값을
명시할 수 있으며 단일 신호의 z0, 기존 대칭 쌍의 z_diff는 유지됩니다. study/design
스키마 필드와 옛 정규 입력은 바뀌지 않고 옛 reader는 새 템플릿/quantity를 거부합니다.
입력과 함께 정확한 엔진 커밋·wheel hash를 저장하세요.

기존 sweep·corners·uniform·상관 normal 샘플링은 실패를 재추출하지 않고 보존하며,
모든 행이 완료돼야 통계를 냅니다. 행별 메시 수렴을 보장하지 않습니다. 이 비대칭 쌍은
fixed_pitch_m을 거부합니다. gap 고정 상태에서 폭이 바뀌면 중심 간격도 바뀝니다.
기존 같은 폭 쌍의 고정 피치 규칙은 유지됩니다. 전체 평면 간격 고정은 해당하지 않습니다.

[지정 주파수 재료](material_impedance.md)를 쓰는 공차/역산 변수는 여전히 기하만
허용합니다. z_diff_forward는 교환 대칭을 가정하지 않아 기울어진 횡방향 텐서를
허용하고 z_diff는 계속 거부합니다. 양 끝은 유효해야 하며 한 끝이 이미 허용 오차를
만족하는 경우 외에는 목표를 끼워야 합니다. 요청/세분 메시의 잔차가 모두 허용 오차
안에 들어야 합니다. 단조성·수율 확률·제조 정확도를 보장하지 않습니다.

## 검증 범위

기울어진 재료 시험은 세분 확인의 필요성을 보여 줍니다. edge4 µm에서 100.851 Ω였지만
edge2 µm 재생은 101.172 Ω로 100±1 Ω 관문에서 거부됐습니다. 처음부터 edge2 µm로
시작하면 99.995 Ω, edge1 µm 확인은 100.097 Ω로 같은 허용 오차를 만족했습니다.
특정 시험의 관측값이며 기본 메시의 정확도 보증은 아닙니다.

두께 0인 진공 선로의 독립 영상전하 패널 80→160 변화는 0.3% 미만입니다.
FEM 세분 시 C/전방 Z 오차는 감소하고 최종 2% 미만이어야 합니다. 같은 물리 메시의
독립 scikit-fem 복소 P1 C 비교는 상대 1e-9입니다. 문서의 비대칭 사다리꼴 쌍에서
edge4→1 µm·far .25→.125 mm·grade .2→.1의 복소 C 변화는 1% 미만, 별도 상자/공기
2배 변화도 1% 미만입니다. 좌우 반사 시 독립 메시의 C 순열은 0.5% 안에서 일치합니다.
이는 실측 에칭이나 임의 영역의 정확도 보증이 아닙니다.

독립 대칭 행렬 기하평균식으로 Zc를 1e-10 안에서 대조하며 scalar/대칭 극한과 손실
제외를 별도 검사합니다. 스칼라·기울어진 재료의 저장형 상관 공차와 100 Ω 폭 역산은
입력을 보존하고 요청/세분 잔차 각각 1 Ω 이내여야 합니다. 잘못된 치수와 비유계 실패
행을 숨기지 않습니다. 종방향 폭 변화·skew/굽힘/비아·자동 비대칭 고유모드 추적이나
새 플랫폼 검증은 포함하지 않습니다.

[공차](study.md) · [역산](design.md) · [English](../../../../../packages/sipi/asymmetric_pair.md)
