# 국소 정전용량 공차 분석과 범위 역산

`ApertureStudyDocument`와 `ApertureDesignDocument`는
[`ApertureSectionDocument`](elliptical_aperture.md)의 저장 기하·메시·균일
유전체를 재사용합니다. 선택 대상은 **실수 단위 길이 정전용량(F/m)**입니다.
임피던스, 총 pad 정전용량, 3D 전이 또는 제조 수율을 추론하지 않습니다.
기존 임피던스 study/design 스키마는 바뀌지 않습니다.

```python
from sipi import (RoundConductor, EllipticalAperture, ApertureSectionDocument,
                  ApertureStudyDocument, ApertureDesignDocument)

section = ApertureSectionDocument(EllipticalAperture(
    width=0.8e-3, height=0.8e-3,
    conductors=[RoundConductor("signal", diameter=0.28e-3)], eps_r=3.96,
), mesh={"size": 20e-6, "angular_divisions": 128})
study = ApertureStudyDocument(section, sampling={
    "kind": "sweep", "count": 3,
    "variables": [{"name": "eps_r", "lower": 3.0, "upper": 5.0}],
})
result = ApertureStudyDocument.loads(study.dumps()).analyze()
print(result.failed, dict(result.summary))

goal = ApertureDesignDocument(section, variable="conductor_0_diameter",
    bounds=[0.20e-3, 0.35e-3], target=200e-12, tolerance=0.5e-12)
design = ApertureDesignDocument.loads(goal.dumps()).solve()
print(design.parameter, design.residual, design.refined_residual)
```

## 변수와 선택량

변수는 `width`, `height`, `eps_r`, `tan_delta` 및 `conductor_0_diameter`,
`conductor_0_x`, `conductor_0_y`입니다. 쌍은 인덱스 1도 지원합니다.
인덱스는 이름과 무관하게 저장 도체 순서를 따릅니다. 길이는 m이고 좌표는
음수일 수 있습니다. 이 균일 유전체 정전기 모델의 실수 C는 손실 탄젠트와
무관하므로 `tan_delta` 변화로 실수 C 분포나 손실 목표를 예측하지 않습니다.

실수 Maxwell 행렬 C의 선택량은 다음과 같습니다.

| 이름 | 정의 |
|---|---|
| `c11` (기본값) | C11 |
| `c22` | C22 |
| `mutual` | −C12 |
| `differential` | (C11+C22−2C12)/4 |
| `common` | C11+C22+2C12 |

단일 도체는 `c11`만 지원합니다. 차동·공통 값은 단면 문서의 전력 쌍대
전압·전하 정의이며 서로 다른 자기 성분도 유지합니다. 도체당 odd/even
정전용량이나 독립 전파 모드를 의미하지 않습니다.

## 저장 샘플과 실패

엄격한 `sipi.aperture-study/1`은 `schema`, `section`, `quantity`, `sampling`을
저장합니다. 공통 [샘플링 계약](study.md)은 sweep, corners, 시드가 있는
uniform·상관 normal을 지원합니다. 변수는 1–8개, 샘플은 2–10000개입니다.
sweep은 변수 하나, corners는 모든 2^n 끝점 조합입니다. normal은 기존
임피던스 study와 동일한 PCG64·대칭 공분산 제곱근을 사용하며 특이한 양의
준정부호 상관도 지원합니다. 미지/누락 필드, 중복 키, 숫자 위치의 bool,
비유한 값과 미지원 버전은 거부합니다. 입력 JSON에 결과를 넣지 않습니다.

유계 입력의 모든 모서리를 계산 전에 확인하지만 **중간 기하가 전부 유효하다는
보장은 아닙니다**. 양 끝점이 유효해도 이동 도체가 다른 도체를 가로지를 수
있습니다. 실제 각 행을 검사하며 normal·중간 위치의 실패는 매개변수·오류
종류·메시지를 보존합니다. 버리거나 재추출하지 않습니다. 입력 생성부터
실패하면 `document`가 없습니다. 결과와 매개변수 스냅샷은 공개 API에서 읽기 전용입니다.

`analyze(max_evaluations=128)`은 장 계산 전에 예산을 검사합니다. 각 행은
저장된 명목 크기·각도 분할로 재메시합니다. 행마다 수렴을 확인한 것은 아닙니다.
전부 성공한 경우만 최소·최대·평균·표본 표준편차(n−1 분모)·선형 보간
5/95 백분위수를 F/m로 제공합니다. corners와 sweep은 무작위 제조 모집단이
아닙니다. 실패가 있으면 `summary=None`입니다.

## 범위 역산과 검증

엄격한 `sipi.aperture-design/1`은 `schema`와 함께 `section`, `variable`,
정렬된 `bounds`, `quantity`, `target_f_per_m`, `tolerance_f_per_m`,
`max_evaluations`를 저장합니다. 목표·절대 오차는 양수, 예산은 3–10000입니다.
끝점이 허용 오차 안에 있는 경우 외에는 끝점 값이 목표를 사이에 두어야 합니다.
이분법은 연속이며 유효한 구간을 전제로 하며 중간 기하의 유효성이나 해의
유일성을 보장하지 않습니다. 평가 실패 시 탐색을 중단합니다.

마지막 평가 하나는 저장 장 크기 절반·각도 분할 두 배의 세분 검증에 예약합니다.
**요청 메시와 세분 메시 모두** 같은 목표 허용 오차를 만족해야 성공합니다.
`CapacitanceGoalError`는 세분 실패를 포함한 완료 이력과 가능한 경우 실패
매개변수를 보존합니다. 성공 결과에는 요청 메시 문서, 두 정전용량·잔차,
이력·입력 JSON이 있습니다. 세분 일치가 보편적인 물리 정확도 보장은 아닙니다.

## 검증

원형 해석해로 유전율 sweep과 200 pF/m 목표 지름을 대조합니다. 두 잔차는
0.5 pF/m 이하, 지름은 해석값 대비 0.5% 이내가 기준입니다. 타원 쌍의 차동
130 pF/m 목표는 두 잔차 1 pF/m 이하입니다. 음수 좌표 목표, 모든 쌍 선택량의
명시적 전압·전하 에너지, 독립 통계 모멘트·공분산·분포, 실패 샘플 보존 및
실제로 최종 세분에서 탈락하는 거친 메시도 확인합니다. 이전 임피던스 study의
JSON과 결정적 샘플은 이전 검증에서 바이트 단위로 동일함을 확인합니다.

[English](../../../../../packages/sipi/aperture_studies.md)
