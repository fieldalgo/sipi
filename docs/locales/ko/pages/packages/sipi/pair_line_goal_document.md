# 두 변수 전방 임피던스 목표 저장

[English](../../../../../packages/sipi/pair_line_goal_document.md) ·
[직접 API](pair_line_goal.md) · [기존 저장 목표](line_goal_document.md)

`ForwardPairDesignDocument`는 순서 있는 기하/재료 변수 두 개와 명시적
유손실 전방 전류 목표 두 개를 저장합니다. 스키마는 `sipi.forward-pair-design/1`이며
root 키는 `schema`, `study`, `conductor`, `targets_ohm`, `tolerances_ohm`,
`initial`, `max_evaluations`의 일곱 개입니다. 목표/허용치 객체는 각각
`differential_forward_impedance_real`, `common_forward_impedance_real`
두 키만 가지며 값은 양의 유한 ohm입니다. 직접 API의 서로 다른 Ic=0/Id=0
전방 입사 정의와 비대칭 복소 결합을 유지합니다.

## 저장과 실행

내부 `impedance-study/3` 또는 `/4`는 `z_diff_forward` 쌍 단면 입력,
양의 고정 주파수, 순서 있는 양의 유계 변수 두 개의 `corners` 규칙을 제공합니다.
이 표시는 쌍 입력 계약만 선택하며 준정적 study나 corner field 계산을
실행하지 않습니다. 기하 단위는 m, 주파수는 Hz, 전도도는 S/m입니다.

짧은 예제는 검증한 초기점에서도 필수 메시 세분을 수행합니다. 전체 폭/간격
검색은 `initial=[.7e-3, .35e-3]`, 문서와 외부 실행 예산 모두
`max_evaluations=64`로 바꾸면 됩니다. 수치 시험은 이 전체 검색을 실행합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.pair_line_goal_document import ForwardPairDesignDocument
from sipi.execution import normalize_saved, execute_saved

def surface(conductivity, rms):
    return dict(conductivity=conductivity, relative_permeability=1.,
                roughness=dict(kind='hammerstad', rms_m=rms))

study = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3,
         substrate_height=.5e-3, eps_r=4., tan_delta=.02,
         left_thickness=35e-6, right_thickness=50e-6,
         box_width=24e-3, air_height=10e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.4e-3, upper=.9e-3),
        dict(name='gap', lower=.2e-3, upper=.6e-3)]))
quantities = ('differential_forward_impedance_real',
              'common_forward_impedance_real')
doc = ForwardPairDesignDocument(study,
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': surface(58e6, .5e-6),
                    'negative': surface(35e6, 1e-6)},
        reference=surface(58e6, 0.), ground_thickness=35e-6),
    targets=dict(zip(quantities, [110., 40.])),
    tolerances=dict(zip(quantities, [.25, .125])),
    initial=[.6013576047896128e-3, .4103854246303812e-3],
    max_evaluations=2)
assert doc.to_dict()['schema'] == 'sipi.forward-pair-design/1'
assert normalize_saved(doc.dumps()) == doc.dumps()
result = ForwardPairDesignDocument.loads(doc.dumps()).solve()
```

외부 예산이 문서의 전체 시도 예산을 수용해야 계산을 시작합니다. callback·코드·
파일 경로·네트워크 동작은 직렬화하지 않습니다. 정규 입력은 변수 순서를
보존하고 목표 객체는 삽입 순서 대신 명시적 키를 사용합니다.

```python
import json
import numpy as np
report = execute_saved(doc.dumps(), max_evaluations=2)
assert report['status'] == 'complete'
assert report['input'] == doc.to_dict()
assert report['result'] == result.to_dict()
assert report['result']['quantities'] == list(quantities)
assert report['result']['evaluations'] == 2
assert np.all(abs(np.array(result.residuals)) <= result.tolerances)
assert np.all(abs(np.array(result.refined_residuals)) <= result.tolerances)
json.dumps(report, allow_nan=False)
```

## 사전 검사와 실행 계약

파싱은 명목/네 모서리 기하·재료와 초기 선로를 메시 없이 검사합니다.
initial이 null이면 각 경계 중간점이며 명시 초기점은 닫힌 경계 안에 있어야
합니다. 평가 예산은 2~10000의 정수입니다. 불리언·비유한 수·중복/알 수 없는
키·미지원 스키마를 거부합니다.

기존 중심 pitch, 전체 층 높이, 형식 있는 재료 모델, 수치 재료 leaf 결합
규칙을 유지합니다. 명목 입력에서 결정한 메시 제어값을 재사용합니다.
conductor는 고정한 명시적 line/6 레코드이며 명목/초기 선로가 이를 검사합니다.
모든 모서리의 도체 유효성이나 내부 전체의 물리적 유효성을 보증하지 않습니다.
사전 검사는 solve 시도 예산 밖이며 최악값·통계 평가가 아닙니다.

계산은 직접 두 변수 API에 위임합니다. 캐시되지 않은 시도 계수, 원래 실패,
예약된 최종 세분, 두 목표 검사를 유지합니다. 선택/세분 입력은 길이 0,
네트워크 기준 50 ohm인 line/6이며 기준값은 Zdd/Zcc를 정의하지 않습니다.
source 샘플링·clipping·재표본·물리 모델 자동 보정은 하지 않습니다.

직접 목표 실패 시 `execute_saved`는 `status='failed'`와 완료 history,
attempts, stage, 실패 변수, 원인 형식·메시지, 가능한 실패 입력을 반환합니다.
미해결 시도를 성공 행으로 바꾸지 않습니다. 목표 문서에서는 최상위 선로용
선택 diagnostics를 거부합니다. 직접 결과에서 전체 R/L/G/C를 검사할 수
있으며 저장 실행 보고서는 전송 방식에 의존하지 않습니다.

## 검증과 한계

독립 modal known-root에서 저장/직접/실행기 보고서를 대조하고 변수 순서,
엄격한 입력, 선행 field 계산 없음, pitch/stack, 재료 leaf factory를 검사합니다.
실행 adapter가 원래 실패/예산 정보를 보존하고 기존 정규 입력을 그대로 유지합니다.

위 1 GHz 비대칭 폭/간격의 전체 검색은 직접 API와 입력/history가 정확히 같고
요청/세분 R/L/G/C가 1e-10 이내입니다. 두 메시의 두 목표가 (.25,.125) ohm을
만족하고 각 메시 변화가 0.5% 이하여야 합니다. 세분된 36/15, 48/20 mm
box/air도 동일 목표 허용치·0.5% 상대 기준을 만족해야 합니다. 시험이
명시적으로 확인하는 1 GHz에서 공통 전류의 연속 절대 변화는 감소하고,
두 차동 인접 변화는 최소 영역 결과 절댓값의 1e-4 이하여야 합니다.
이는 [직접 시험의 유한 민감도 기준](pair_line_goal.md)이며 일반 주파수나
무한 영역 오차 상한이 아닙니다. 독립 balanced 2N 고유공간으로 Zc/Zdd/Zcc를 1e-10 이내
비교합니다. 균질 PEC 쌍의 두 재료 leaf에서는 양쪽 메시의 독립 SPD 진공
특성 행렬을 복소 유전체로 scaling하여 1e-10 이내 대조합니다. 후자는 목표에
맞는 초기점에서 시작하며 두 leaf 해의 유일성을 증명하지 않습니다. 이러한
비교는 추출 RLGC 또는 진공 field를 재사용하며 독립 기하 추출·실측을 대신하지 않습니다.

유한 영역 검증으로 무한 영역 오차·유일/전역 최적해·full-wave 정확도·제조 수율·
신규 플랫폼을 보증하지 않습니다. 직접 API의 자원/물리 유효 범위가 적용되고
기존 목표와 study 스키마는 종전 입력 계약을 유지합니다.
