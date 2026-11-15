# 양면 접지 면별 금속 제조 표본

[English](../../../../../packages/sipi/two_ground_face_pair_study.md)

`sipi.two_ground_face_pair_study`의 `TwoGroundFaceForwardPairStudyDocument`는
`sipi.two-ground-face-forward-pair-study/1`을 저장한다. 기존의 순서 있는 제조 표본
루프에서 각 [면별 금속 선로](two_ground_face_panel_line.md)의 두 실수 전방 여기
임피던스를 계산한다. 전체 경계 연구와 이전 스키마는 그대로이며 명시적으로 import한다.

루트 키 여섯 개는 schema·study·conductors·reference·ground_thickness_m·panel이다.
중첩 study/3 또는 /4가 쌍 선로 템플릿·양수 주파수 하나·순서 있는 기하/재료 변수·
표본과 기존 fixed-pitch 제약을 제공한다. 면별 금속과 접지 금속 법칙은 표본 간 고정이다.
새 생성자의 기본 보간 차수는 16이며 기존 기본값은 그대로다. 미지/누락 키·중복 JSON
키·비유한 값을 거부한다.

corners·sweep·uniform·normal 표본의 원래 순서·seed·상관을 보존한다. nominal 입장은
장 계산 없이 확인한다. 전체 표본 수가 max_evaluations(2..10000) 안에 들어야 장 계산을
시작한다. 중복을 포함해 각 표본을 개별 행으로 시도한다. 무효 기하/재료 입력과
추출/진단 실패를 기록하고 이후 행도 계속한다. 잘라내기·삭제·재표본·재시도·재가중은
없으며 중단은 전파한다. Re(Zdd)와 Re(Zcc)는 함께 성공하거나 실패한다. 전체 복소
특성 행렬의 별도 Ic=0/Id=0 여기이며 서로 분리된 모드 근사값이 아니다.

행은 표본 값·해석한 매개변수/재료·원래 면별 선로 입력·실패 단계/종류/원인과 확보한
면별 전류·유전체 메시 기록을 보존한다. 불변 결과는 모든 행이 성공한 경우에만 기술
통계를 제공한다. 제조 수율 신뢰구간이나 실측 공정 정확도 주장이 아니다. 임의 표본
각각의 자동 수렴 보장도 아니다. 기반 선로의 유한 기하·패널/자원·표피 깊이·잔여 코어
검사는 계속 적용한다.

공통 저장 실행·요청·기록·프로젝트·CLI는 완료/불완료 상태와 원래 실패 행을 보존한다.
기록/프로젝트를 복원할 때 장 계산을 다시 하지 않는다. 다음 예제는
[준비한 쌍 선로 목표](two_ground_face_pair_goal_document.md)를 계산 없이 네 모서리
표본 연구로 바꾼다.

```python
from sipi.two_ground_face_pair_study import TwoGroundFaceForwardPairStudyDocument

# `goal` is a prepared TwoGroundFaceForwardPairDesignDocument.
source = goal.to_dict()
study = TwoGroundFaceForwardPairStudyDocument(source["study"],
    conductors=source["conductors"], reference=source["reference"],
    ground_thickness=source["ground_thickness_m"], **source["panel"])
text = study.dumps()
assert TwoGroundFaceForwardPairStudyDocument.loads(text).dumps() == text
assert study.samples().shape == (4, 2)  # Two-variable corners source.
# Explicit field work: result = study.analyze(max_evaluations=4)
```

검증은 독립 모드 해/통계·상관된 무효 표본·재료 연결·행별 원래 오류·CLI/프로젝트
복원을 포함한다. 등록 물리 모서리는 폭 0.43/0.44 mm×간격 0.28/0.30 mm,
8×2 mm 상자, epsilon_r 4/tan_delta 0.003, 2 GHz다. 각 모서리를 패널 64/128/256에서
R/L/C0 상대 변화 0.01과 독립 행렬 제곱근 전방 행렬 1e-10으로 검사한다. 대각선 양끝
모서리는 256 패널에서 메시 반감과 유한 폭 8/16/32 mm를 별도로 원래 0.01 기준으로
검사한다. 동반 기록에 실제 결과를 명시한다. 선택된 유한 사례의 근거이며 무한 영역·
임의 형상·브라우저/플랫폼·실측 인증이 아니다.

[스칼라·단일 쌍 여기의 표본](two_ground_face_line_study.md)

[IID 합격 평가와 미해결 표본](two_ground_face_yield.md)
