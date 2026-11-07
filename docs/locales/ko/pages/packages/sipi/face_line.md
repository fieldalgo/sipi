# 신호 면별 손실을 저장하는 선로 입력

[English](../../../../../packages/sipi/face_line.md)

[버전 5](reference_line.md)는 기준면·측벽·ground trace도 각각 저장합니다.

`sipi.transmission-line/4`는 [공통 메시 선로 문서](line_model.md)에 명시적인
`surface-faces` 도체 입력을 추가합니다. 검증된 [신호 면별 표면 모델](face_conductor.md)과
기존 유전체·network·회로 API를 재사용하며 다른 field 근사를 새로 만들지 않습니다.

```python
import json
from sipi import microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.execution import normalize_saved, execute_saved

cross = CrossSectionDocument(microstrip(width=.5e-3, substrate_height=.5e-3,
    thickness=35e-6, eps_r=4., air_height=1e-3, box_width=4e-3),
    mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
def metal(rms=0.):
    return dict(conductivity=58e6, relative_permeability=1.,
        roughness=dict(kind="hammerstad", rms_m=rms))
conductor = dict(kind="surface-faces", ground_thickness=35e-6,
    conductors={"signal": dict(bottom=metal(.5e-6), top=metal(),
                               left=metal(), right=metal())}, reference=metal())
document = TransmissionLineDocument(cross, [1e9, 4e9], materials={},
    conductor=conductor, length=.03, schema="sipi.transmission-line/4")
text = normalize_saved(document.dumps())
report = execute_saved(text, diagnostics=["characteristic"])
assert report["status"] == "complete"
faces = report["result"]["conductor_boundaries"]
assert len(faces["labels"]) == 5
assert faces["current_flux_error"] <= .05
json.dumps(report, allow_nan=False)
```

## 엄격한 입력·이전 버전 보존

최상위 필드는 기존 `schema`, `cross_section`, `frequency_hz`, `materials`,
`conductor`, `length_m`, `reference_ohms`입니다. conductor는 정확히 `kind`,
`conductors`, `reference`, `ground_thickness`를 갖습니다. kind는 `surface-faces`이며,
conductors는 **모든 신호 이름**을 정확히 bottom/top/left/right가 있는 객체에 연결합니다.
각 면과 공통 reference는 기존 metal record로, conductivity(S/m), relative_permeability,
roughness만 가집니다. roughness는 smooth/Hammerstad/Groiss/causal Huray/Cannonball Huray
중 하나를 기존 필드·유효범위로 명시합니다.

parsing에서 mapping·기하·각 금속/skin-depth 조건을 field 풀이 전에 검사합니다.
알 수 없거나 누락/중복된 키, 비유한 수, 잘못된 금속, 미지원 polygon/두께0 신호,
충분하지 않은 skin depth는 거부합니다. 면의 기본값이나 거칠기 변환을 추정하지 않습니다.
입출력 dictionary는 분리된 snapshot이고 loading/정규화 과정에서 메시·field를 풀지 않습니다.

생성기 기본 버전은 계속 1입니다. 버전1의 공통 surface는 roughness_rms를,
버전2–4는 명시적인 roughness 객체를 사용합니다. 버전3의 신호별/공통reference 계약을
보존하며 버전4도 기존 perfect/surface/surface-boundaries를 받습니다.
버전1–3은 surface-faces를 거부합니다. 이전 판독기가 새 버전을 도체 전체 모델로
조용히 바꾸면 안 됩니다. 미출시 개발 중에는 입력과 함께 정확한 엔진 artifact를 기록하세요.

## 한 메시·C0 공유·출력

analyze()는 단면 메시를 하나 만듭니다. 면별 손실은 진공 전류를 한 번 추출하고
유전체 sweep은 그 C0를 재사용하므로 외부 인덕턴스·표면 전류가 같은 기하/basis를 씁니다.
면별 R/내부 L과 유전체 C/G·외부 L을 기존 RLGC network로 합성하고 정규 입력과
직접 FaceConductorLoss 객체를 보존합니다. 기존 depth·good-conductor·flux·거칠기
유효범위를 변경하지 않습니다.

공통 실행은 R/L/G/C·S·이름/주파수·선택적인 characteristic/mode 진단을 보존합니다.
conductor_boundaries에는 순서 있는 labels, skin depth, roughness factor,
복소 surface impedance, 면/reference별 저항 기여를 남깁니다. 면별 결과는 추가로
surface_current_factors_per_m(Q), current_integrals, whole_boundary_current_integrals,
current_flux_error를 보존합니다. Q는 (4N+1,N,N), 면별/전체 도체 적분전류는
(4N+1,N)/(N+1,N)이며 마지막 항은 reference입니다. 분할 보존을 확인할 수 있는
진단값이고 저항 정확도 인증은 아닙니다. 기존 도체별 출력에 새 면별 필드를 끼워 넣지는 않습니다.

기존 circuit/assembly/transform source의
`{"kind":"transmission-line", "document": ...}` 경로로 새 선로를 재사용합니다.
새 transport·회로 schema는 필요하지 않습니다. 저장 선로의 실행 성공과
물리 유효성·수렴·앱 UI 지원·플랫폼 수락은 별개입니다.

저장 RLGC/S와 직접 face/주파수 유전체 API의 일치 `1e-10`, 버전3/4 기존 도체형식
동치 `1e-12`, 정확히 한 메시/C0 공유·snapshot/replay·풀이 없는 parsing을 검사합니다.
면별 진단·종단회로 재생 `1e-10`과 기존 line/boundary/execution 회귀도 검사합니다.
물리 field/면/메시 수락 기준은 링크한 모델을 따릅니다. reference 면 분리,
실측 동박 보정·전체 앱/플랫폼 parity는 별도 작업으로 남습니다.
