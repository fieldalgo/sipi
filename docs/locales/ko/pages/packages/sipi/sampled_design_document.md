# 명시 주파수 샘플 목표 저장

`SampledImpedanceDesignDocument`는 `sipi.sampled-impedance-design/1`로 이름 있는
템플릿 변수를 [주파수 샘플 역산 API](sampled_design.md)에 연결합니다. 양의 범위를
가진 정확히 두 변수와 한 실수 준정적 물리량(`z0`, `z_diff`, `z_common`)을 2~64개의
명시 주파수에서 저장합니다. 호환되는 템플릿은 기존 scalar/대칭쌍 study registry를
재사용하며 함수나 실행 코드를 직렬화하지 않습니다.

예제는 기준 치수에서 시작하므로 요청/세분 메시 두 번을 평가합니다. 먼 초기점은
`initial=[.35e-3,5.5]`, 예산 64처럼 더 큰 저장 예산이 필요합니다.

```python
from sipi import SampledImpedanceDesignDocument
from sipi.dielectric import DebyeDielectric
from sipi.execution import normalize_saved, execute_saved

goal = SampledImpedanceDesignDocument('coupled_stripline',
    dict(width=.5e-3, gap=.1e-3, plane_spacing=1e-3, eps_r=1., box_width=8e-3),
    variables=['width','strength'], bounds=[[.3e-3,.7e-3],[2.,6.]],
    frequencies=[1e8,1e10], targets=[57.23463009022641,97.84159316427296],
    tolerances=[.5,.5], quantity='z_diff', max_evaluations=2,
    mesh=dict(edge_size=1e-6,far_size=.125e-3,grade=.1),
    materials={'dielectric':DebyeDielectric(2.,[4.],[1e9])},
    material_variables={'strength':dict(region='dielectric',path=['strengths',0])})
text = goal.dumps()
assert normalize_saved(text) == text
out = execute_saved(text, max_evaluations=2)
assert out['status'] == 'complete'
assert out['result']['frequencies_hz'] == [1e8,1e10]
assert out['result']['evaluations'] == 2
assert all(row['quantity']=='z_diff' for row in out['result']['history'])
assert all(abs(r)<=.5 for r in out['result']['refined_residuals_ohm'])
```

## 엄격 입력 계약

필수 최상위 필드는 `schema`, `template`, `parameters`, `variables`, `quantity`,
`frequencies_hz`, `targets_ohm`, `tolerances_ohm`, `initial`, `max_evaluations`,
`mesh`, `fixed_pitch_m`, `fixed_plane_spacing_m`, `materials`, `material_variables`입니다.
미지 필드/버전·중복 키·비유한 값은 거부합니다. 정규화는 분리된 표준 입력 복사본을
반환하며 장해석이나 최적화를 수행하지 않습니다.

`variables`는 순서 있는 두 객체이며 각각 `name`과 양의 엄격한 증가 `bounds`를
갖습니다. `initial`은 null(중간점) 또는 범위 안의 두 값입니다. 주파수는 유한·0 이상·
엄격한 오름차순이고 목표와 절대 허용 오차는 같은 길이의 양수 벡터이며 Ω 단위입니다.
변수 일괄 평가 예산은 2~10000 정수입니다. 목표와 별도로 주파수만 자동 정렬하지 않습니다.

`materials`는 영역 이름과 인코딩한 유전체 모델의 객체입니다. 빈 override는 기하의
`eps_r` 같은 유전체 변수 지원을 유지합니다. 비어 있지 않으면 기존 study의 중복 기하
물성 입력 금지를 유지합니다. `material_variables`는 기하만 조정할 때 빈 객체이며,
그 외에는 등록한 별칭 1~2개를 `region`, 모델 `parameters` 아래 `path`로 기존 서로
다른 숫자 필드에 연결합니다. 경로·형식·이름 규칙은 기존 study를 따릅니다. 재료 별칭
두 개가 식별 가능성이나 유일해를 뜻하지 않습니다. 기존 고정 pitch·전체 평면 간격
제약은 함께 사용할 수 있습니다.

## 모든 주파수의 사전 검사

첫 주파수의 study validator로 명목·모서리 입력과 기하/메시 제약을 확인합니다.
추가 검사는 명목·네 모서리·명시 또는 기본 초기점의 기하와 샘플 모델을 **모든**
주파수에서 검증합니다. 이 추가 검사에서 생성한 각 기하는 주파수 목록 전체에 재사용합니다.
메시를 만들지 않으며 solve 일괄 평가 예산 밖입니다. 연속 범위 전체의 유효성을
증명하는 검사는 아닙니다.

첫 주파수의 유효성만으로 충분하지 않습니다. 회전한 두 재료 주축의 복소 값이 어떤
주파수에서는 같고 다른 주파수에서는 달라져 쌍 입력이 무효가 될 수 있습니다.
또한 대각 텐서인 양끝 사이의 초기점이 기울어진 텐서일 수도 있습니다. 이런 경우는
탐색 시도까지 미루지 않고 장해석 전에 거부합니다. 탐색에서 방문하는 다른 내부점의
실패는 기반 API가 계속 이력으로 보존합니다.

## 실행·재현·범위

`solve()`는 이름 있는 기하/재료 함수를 구성해 기존 `SampledImpedanceDesign`을
반환합니다. `execute_saved()`는 기존 `sipi.execution/1` 외곽 구조·입력 바이트 제한·
diagnostics 규칙을 사용합니다. 호출자 `max_evaluations`가 저장 일괄 평가 예산을
충족해야 하며 자동으로 줄이지 않습니다. 한 batch는 한 변수 쌍의 시도이며 주파수별
내부 solve 수가 아닙니다. 주파수 목록은 별도로 64개까지입니다. 두 번의 batch가
두 개보다 많은 주파수를 평가할 수 있습니다. 시간·메모리 보장은 아닙니다.

성공 결과에는 선택 값·물리량/주파수·두 메시 입력·재료 sweep·이력이 있습니다.
탐색 재현은 목표 JSON, 개별 행 재현은 그 행의 물리량·기하·재료 sweep을 사용합니다.
실패는 `status='failed'`, `result=None`과 실제 시도 수·단계·실패 변수·원인 종류·
가능한 현재 입력·행마다 모델을 가진 완료 이력을 반환합니다. 잘못된 입력이나 부족한
호출자 예산은 solve 전에 예외를 발생시킵니다.

수락 시험은 엄격 파싱·복사·변수/주파수 순서·재료 연결·기하 유전체 변수·제약·모든
주파수/초기/모서리 모델 검사·예산·실패 전달을 확인합니다. 같은 표준 입력에서 실제
저장 실행은 raw API와 같습니다. 위 얇은 Cohn 사례는 요청/세분 및 독립 식에서 주파수별
.5Ω를 만족해야 합니다. 먼 초기점 복원과 외곽 수렴은 기반 API의 별도 검증을 재사용합니다.
명시한 주파수 지점만 제약하며 연속대역·전역해·실측 재료 식별을 보장하지 않습니다.
앱 엔진을 자동 갱신하거나 브라우저/Windows 지원을 확정하지 않으며 이전 reader는
이 스키마를 거부합니다.

[주파수 API](sampled_design.md) · [실행](execution.md) ·
[English](../../../../../packages/sipi/sampled_design_document.md)
