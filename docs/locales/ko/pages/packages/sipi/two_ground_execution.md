# 양면 접지 저장 실행

[English](../../../../../packages/sipi/two_ground_execution.md)

공통 실행 registry는 `sipi.two-ground-panel-transmission-line/1`을 기존 정규화·실행 요청·
결과 기록·프로젝트·CLI API에 등록한다. [저장 선로 계약](two_ground_panel_line.md)과
[표면 전류 제한](two_ground_conductor.md)은 그대로다. 공유 기능은 `dependencies.json`의
정확한 리비전에서 제공한다. 기존 추출 기본값은 유지하며 기능이 없으면 실패한다.
설치 산출물 검사로 실제 구현을 식별한다. 사용 예제는 영문 문서와 같다.

준비·정규화에는 장 계산이 없다. 주파수 개수는 전류·체적 계산 전에 max_evaluations
이하여야 한다. 예산은 주파수별 완전한 평가를 세며 내부 행렬 연산 수를 세지 않는다.
기존 일반 예산 상하한과 입력 바이트 제한을 유지한다. 선택적 characteristic/modes
진단은 기존 계약을 사용하고 진단 거부가 있어도 완료된 기본 결과를 보존한다.

완료 결과는 SI R/L/G/C, 네트워크·진단, 개별 도체 표면 이름·표면 임피던스·표피 깊이·
거칠기 계수·저항 기여·전류 Gram 행렬·부호 전류를 담는다. `current_solver`는 정확한
패널 설정·진공 C0·그룹 및 개별 전류 관측·수치 진단을 보존한다. `dielectric_mesh`는
실제 체적 메시를 식별한다. 식별자나 작은 잔차만으로 수렴을 입증하지 않는다.

형식화된 선로 실패는 failed 상태, null 결과, 원래 단계·원인·입력·전류·메시 기록을
반환한다. 공유 기능이 없으면 전류 단계 RuntimeError이며 성공이나 자동 대체 계산으로
표시하지 않는다. SavedExecutionRecord는 요청 해시와 원문에 실행 영수증을 묶고,
SavedProject는 기존 API로 이를 보존·선택한다. artifact 항목은 host-declared이며
저장 기록에 있다는 이유로 검증된 것이 아니다. 실제 artifact 동일성은 별도의
설치 wheel 감사 기록이 뒷받침한다.

기존 `python -m sipi validate input.json` 또는
`python -m sipi run input.json --output result.json`을 사용한다. CLI 종료 코드는
그대로다. 입력·준비 오류는2, 계산 실패(실행 단계의 장 계산 전 모델 예산 거부 포함)는1,
출력 거부·오류는3이다. 실패 영수증이 있으면 보존하며 출력 파일을 조용히 덮어쓰지
않는다. 이번 단위는 브라우저 Worker/UI·목표 역산·공차·공개 배포·Windows 실행파일
지원을 추가하지 않는다.
