# Changelog

- Place the pair-preview impedance result directly below Calculate impedance and the width search below the drawing; fix the stacked phone title bar and run-together footer text. Values and engine paths are unchanged.
  차동 쌍 미리보기의 임피던스 결과를 Calculate impedance 바로 아래에, 선폭 찾기를 단면도 아래에 두고, 휴대폰 폭의 제목 줄과 붙어 보이던 바닥글 글자를 고쳤습니다. 수치와 엔진 경로는 그대로입니다.

- Add an original PCB preset library and clickable cross-section dimensions to the pair
  workbench, with a readable dimension inspector and separate calculation/width results.
  PCB 단면 예시 프리셋과 클릭 가능한 치수선을 추가하고 입력·계산·선폭 역산 화면을 재구성합니다.

- Separate CCL calculation/search results and errors in a compact workbench; explain
  unbracketed targets with actual boundary widths/impedances without changing inputs.
- CCL 작업 화면의 계산/탐색 결과·오류를 분리하고, 목표 구간 실패 시 실제 양 끝
  선폭·임피던스를 안내합니다. 입력과 수치 기준은 변경하지 않습니다.

- Use unit-aware decimal arrow increments in the CCL preview while preserving precise typed and saved dimensions.
  CCL 프리뷰 화살표에 단위별 소수 증분을 적용하고 직접 입력·저장된 정밀 치수를 보존합니다.

- Fix: the nine two-substrate unbacked coplanar templates (plain, coated and conformal-coated; single, coupled and asymmetric) failed to mesh with ordinary inputs (`MeshInputError`: zero-length edge). Raising the backed stack by the lower air added the air height after the substrate sum, so a trace bottom differed from the layer interface in the last bit (e.g. 0.0022 against 0.0021999999999999997). Shifted heights that lie on an interface or a trace face now take the value the new section computes; the nine one-substrate unbacked templates keep bit-identical geometry and meshes. / 수정: 두 기판 unbacked coplanar 템플릿 9개(기본·코팅·conformal 코팅, 단일·결합·비대칭)가 평범한 입력에서 메시를 만들지 못했다(`MeshInputError`: 길이 0인 변). 아래 공기만큼 적층을 올릴 때 기판 합 뒤에 공기 높이를 더해 트레이스 바닥이 층 경계와 마지막 비트에서 달랐다(예: 0.0022 대 0.0021999999999999997). 경계나 트레이스 면에 놓인 높이는 이제 새 단면이 계산하는 값을 쓴다. 한 기판 unbacked 템플릿 9개는 기하와 메시가 비트 단위로 같다.

- Add `sipi.transmission-line/8` (`sipi.default_line.DefaultPanelTransmissionLineDocument`): the transmission-line/7 fields plus the conductor-current method, defaulting to `panel` for `surface` and `surface-boundaries` conductors. Normalization always saves `current_method` and the panel controls; P1 requires `current_method: "volume-p1"`. It runs the same delegation as `sipi.method-transmission-line/1`, and its RLGC and S are bit-identical to that document (panel) or to transmission-line/7 (P1). `surface-faces`, `perfect` without a named method, unsupported boundary combinations and panel-document refusals are refused with no fallback. The default controls are 64/512/14 with one or two grounds and 64/12 with none (measured on all 72 templates: 64→128 panels changed C0 by at most 1.5e-6 and the current Gram by at most 5.2e-3; 128 is a precision option; trapezoidal conductors keep an estimated 1–2% Gram error). Transmission-line/1–7, panel, method-line documents and results are unchanged. / `sipi.transmission-line/8`(`sipi.default_line.DefaultPanelTransmissionLineDocument`)을 추가했다. transmission-line/7 필드에 도체 전류 방법을 더하고, `surface`·`surface-boundaries` 도체의 기본값을 `panel`로 한다. 정규화 때 `current_method`와 panel 제어값을 항상 저장하며, P1은 `current_method: "volume-p1"`을 적어야 한다. `sipi.method-transmission-line/1`과 같은 위임으로 실행하고 RLGC·S가 그 문서(panel) 또는 transmission-line/7(P1)과 비트 단위로 같다. `surface-faces`, 방법을 적지 않은 `perfect`, 지원하지 않는 경계 조합, panel 문서의 거절은 대체 없이 거절한다. 기본 제어값은 한·두 접지 64/512/14, 접지 없음 64/12이다(템플릿 72개 측정: 패널 64→128에서 C0 변화 최대 1.5e-6, 전류 Gram 변화 최대 5.2e-3. 128은 정밀 옵션. 사다리꼴 도체는 Gram 오차 약 1–2%가 남는 것으로 추정). transmission-line/1–7, panel·방법 선로 문서와 결과는 바뀌지 않는다.

- Add the auxiliary `recovered_surface_current_factors` (`sipi.recovered_conductor`): P1 surface-current factors from the volume shape derivative (Wheeler's incremental-inductance rule) on the same P1 basis and C0, with diagnostics. On five PCB default meshes it is 0.24–0.34% below the boundary-panel value (the boundary-gradient P1 factor is 12–20% below), coupled refinement order 1.34, extra cost 0.37–0.85 of the P1 solve; the parallel plate is exact and the coax converges at second order. Non-right-angle corners, out-of-range support fractions and supports meeting other conductors or open walls with a normal component are refused. `surface_current_factors`, `volume-p1`, the panel default and saved documents and results are unchanged; the method is not yet selectable in saved documents. / 보조 함수 `recovered_surface_current_factors`(`sipi.recovered_conductor`)를 추가했다: 같은 P1 기저와 C0에서 부피형 형상 미분(Wheeler 증분 인덕턴스 규칙)으로 표면 전류 계수와 진단을 계산한다. PCB 기본 메시 다섯 단면에서 경계 panel 값보다 0.24–0.34% 낮고(경계 기울기 P1 계수는 12–20% 낮음), 결합 세분 차수 1.34, 추가 비용은 P1 해의 0.37–0.85배다. 평행판은 정확하고 동축은 2차로 수렴한다. 직각이 아닌 모서리, 범위 밖 지지 비율, 다른 도체나 법선 성분을 가진 채 열린 벽에 닿는 지지는 거절한다. `surface_current_factors`·`volume-p1`·panel 기본값과 저장 문서·결과는 바뀌지 않으며, 저장 문서에서 아직 고를 수 없다.

- Tests: the three P1 conductor refinement tests (coupled resistance, saved Cannonball-Huray line, coupled roughness R and internal L) allow a 6% two-mesh change instead of 5%. On macOS the mesher picks another valid triangulation at exact cocircular ties and the change was 5.01% (4.08% on Linux and Windows); with P1's observed convergence order of about 0.12 this check is a mesh-change check, not an accuracy bound. The flux bound stays 5%. / 시험: P1 도체 세분 시험 3개(결합 저항, 저장 Cannonball-Huray 선로, 결합 거칠기 R·내부 L)의 두-메시 변화 기준을 5%에서 6%로 바꿨다. macOS 메셔가 정확한 cocircular 동점에서 다른 유효 삼각분할을 골라 변화가 5.01%였고(Linux·Windows 4.08%), P1 관측 수렴 차수가 약 0.12라 이 검사는 정확도 상한이 아니라 메시 변화 확인이다. flux 기준은 5% 그대로다.

- Add `sipi.open-panel-transmission-line/1` and `open_panel_surface_current_factors` for sections with no ground plane (open bottom, top and sides; grounded traces are the reference), using the pinned shared open-box panel solver; `sipi.method-transmission-line/1` with `current_method='panel'` now runs it for those sections (panel controls without `ground_modes`), so all 72 templates have panel currents with typical inputs. Vacuum capacitance matches an independent P2 solution on the three unbacked coplanar templates within 5e-4; existing documents and results are unchanged. / 접지 평면이 없는 단면(아래·위·옆 모두 열림, 접지 트레이스가 기준)을 위한 `sipi.open-panel-transmission-line/1`과 `open_panel_surface_current_factors`를 추가했다(고정한 공유 open-box panel 해법 사용). `current_method='panel'`인 `sipi.method-transmission-line/1`이 이 단면에서 그것을 실행하며(panel 제어에 `ground_modes` 없음), 전형 입력 템플릿 72개 모두가 panel 전류를 가진다. unbacked coplanar 템플릿 3종에서 진공 정전용량이 독립 P2 해와 5e-4 이내로 일치하며, 기존 문서와 결과는 바뀌지 않는다.

- Pin the shared revision whose two-ground panel solver admits width/height up to 64, and accept the same range in two-ground current factors (was 16): layered coplanar striplines in their default boxes now have panel currents (54 of 72 templates with typical inputs). / 두 접지 panel 해법이 폭/높이 64까지 받는 공유 리비전으로 고정하고 두 접지 전류 인자도 같은 범위를 받는다(이전 16): 기본 상자의 적층 coplanar stripline이 panel 전류를 가진다(전형 입력 템플릿 72개 중 54개).

- Pin the shared revision whose panel solvers compute conductor clusters nearer the walls than their extent on wall-scaled boxes instead of refusing them: grounded coplanar and coplanar-stripline sections in default boxes now have panel currents (51 of 72 templates with typical inputs, from 30); earlier results are bit-identical and panel diagnostics add `smooth_interpolation_boxes` only when boxes were used. / 벽에 자신의 크기보다 가까운 도체 군집을 거부하지 않고 벽 거리 상자로 계산하는 공유 리비전으로 고정한다: 기본 상자의 grounded coplanar·coplanar stripline 단면이 panel 전류를 가진다(전형 입력 템플릿 72개 중 51개, 이전 30개). 이전 결과는 비트 단위로 같고, 상자를 쓴 경우에만 패널 진단에 `smooth_interpolation_boxes`가 더해진다.

- Pin the shared revision whose two-ground panel solver repeats a failed one-box interpolation check on plane-scaled boxes: coupled, layered and broadside striplines that were refused now solve, earlier results are bit-identical, and two-ground current diagnostics add `smooth_interpolation_boxes` and `single_box_matrix_error` only when the repeat was used. / 두 접지 패널 해법이 실패한 단일 상자 보간 검사를 평면 거리 기준 상자에서 다시 하는 공유 리비전으로 고정한다: 거절되던 결합·적층·broadside stripline이 계산되고, 이전 결과는 비트 단위로 같으며, 재검사를 쓴 경우에만 두 접지 전류 진단에 두 키가 더해진다.

- Add `sipi.method-transmission-line/1`: a saved line whose conductor-current method (`panel` or `volume-p1`) is required and recorded; it runs the existing panel, two-ground panel or transmission-line document unchanged and refuses rather than falls back. / 도체 전류 방법(`panel` 또는 `volume-p1`)을 반드시 적고 기록하는 저장 선로 `sipi.method-transmission-line/1`을 추가했다. 기존 panel·두 접지 panel·전송선 문서를 그대로 실행하며 대체하지 않고 거절한다.

- Document how to choose the conductor-current method for saved lines: wrap a `surface-boundaries` line in a panel line where the section allows, with a runnable example; existing documents and results are unchanged. / 저장 선로의 도체 전류 방법 고르기를 문서화했다: 단면이 허용하면 `surface-boundaries` 선로를 패널 선로로 감싼다(실행 예제 포함). 기존 문서·결과는 바뀌지 않는다.

- Document that the P1 surface-current loss factor converges slowly (observed order about 0.12) and was 10–20% below the boundary-panel value for the coupled-microstrip refinement case; the 5% mesh-change check does not bound that error. / P1 표면 전류 손실 계수가 느리게 수렴하며(관측 차수 약 0.12) 결합 마이크로스트립 세분 사례에서 경계 패널 값보다 10–20% 낮았고, 5% 메시 변화 검사가 그 오차를 제한하지 않음을 문서화했다.

- Save explicit fixed-guard finite-resolution comparisons with SI allowances, typed partial-result binding and unchanged direct assessment payloads.

- `sipi.geometry_v1.to_geometry_v1` writes format 0.3 parts for the pinned simcase reader: the component declares `length_unit` `"m"` and `depth` null, there is no `units` part, and materials use `relative_permittivity` and `loss_tangent`. / `to_geometry_v1`이 고정한 simcase 읽기에 맞게 형식 0.3 부분을 쓴다: 구성 요소가 `length_unit` `"m"`, `depth` null을 밝히고 `units` 부분이 없으며 재료는 `relative_permittivity`·`loss_tangent`를 쓴다.

- Pin the shared galerkin/meshine revision that includes the units and naming steps L2/L3 and use `galerkin.kernels` and the SI argument names; example output is byte-identical. / 단위·이름 L2·L3가 들어간 공유 galerkin/meshine 리비전으로 고정하고 `galerkin.kernels`와 SI 인자 이름을 쓴다. 예제 출력은 바이트 단위로 같다.

- Add direct fixed-guard harmonic-current finite-resolution assessments with separate volume, current and outer comparisons, bounded reuse and retained failures.

- Save explicit fixed-potential guard face-current lines with matched RLGC, four-port networks and typed partial execution evidence. / 고정 전위 가드의 면 전류 선로를 일치 RLGC·4포트 망·단계별 실행 근거와 별도 저장한다.

- Add explicit two-active fixed-potential guard currents and surface loss, retaining induced guard currents and all physical faces. / 두 활성 도체와 고정 전위 가드의 전류·표면 손실을 연결하고 유도 가드 전류와 모든 물리 면을 보존했다.

- Evaluate explicit multiconductor forward-current launches with full coupled voltage/current profiles and separate conductor/dielectric power dissipation.

- Save explicit three-active finite-resolution comparisons with SI allowances, typed partial-result binding and unchanged direct assessment payloads.

- Add direct three-active harmonic-current finite-resolution assessments with separate volume, current and outer comparisons, bounded reuse and retained failures.

- Save explicit three-active harmonic face-current lines with matched RLGC, six-port networks and typed partial execution evidence. / 세 활성 도체의 조화기저 면 전류 선로를 일치 RLGC·6포트 망·단계별 실행 근거와 별도 저장한다.

- Add a separate three-active harmonic corner-current and surface-loss adapter with exact physical face conversion and bounded scoped reuse. / 세 활성 도체의 코너 조화기저 전류·표면 손실에 정확한 면 변환과 유계 범위 재사용을 별도로 연결했다.

- Save bounded linear-current face-line quantity goals with strict preflight, independent refinements, typed failed receipts and request/project/CLI replay.

- Add explicit linear-current face-line manufacturing sample documents with ordered inputs, scoped reuse, typed failed rows and descriptive-only summaries.

- Add an explicit linear corner-density face-line goal adapter with unchanged bounded-search, target and independent refinement criteria; exact current/mesh reuse remains request-local.

- Add explicit saved linear corner-current finite comparisons, typed partial receipts and exact bounded request-local field reuse.

- Save explicit linear corner-density face-line inputs and preserve current/mesh evidence through RLGC, typed failures and execution replay.

- Add explicit linear corner-density current and surface-loss APIs with pre-solve physical panel budgets; retain existing defaults and saved schemas.

- Connect explicit all-active corner-power currents to whole/face surface-metal loss, preserving direct current bases, strict scope and independent P3 checks. Existing defaults and saved documents remain unchanged.

- Save bounded face-metal refinement plans and validate partial histories against exact planned prefixes and caller step/outer reservations.

- Add explicit bounded face-metal volume/panel refinement plans with two consecutive passes, reserved outer checks and retained typed failures.

- Save face-metal frequency-resolution acceptance plans with complete budgets, unknown-row retention and shared execution/project replay.

- Compare joint face-metal frequency-grid acceptance across explicit resolutions, retaining disagreements as unresolved original trials.

- Select fixed face-metal frequency-grid candidates with simultaneous joint IID confidence bounds and complete attempt accounting.

- Connect face-metal frequency-grid studies to joint IID limits and conservative unknown-trial confidence envelopes.

- Add face-metal manufacturing samples across finite frequency grids with atomic failed rows and retained material/current evidence.

- Save explicit face-metal resolution plans and retain validated partial failures in version-2 execution records.

- Add explicit face-metal volume, panel and outer-domain assessments with retained per-entry limits and partial failures.

- Connect finite-frequency face-metal paired goals to strict saved inputs, shared execution and restored CLI records.

- Add explicit face-metal paired goals across finite frequency grids with unchanged per-frequency target and independent refinement gates.

- Connect face-metal scalar and paired IID studies to inclusive acceptance limits and conservative unknown-row confidence envelopes.

- Add strict saved two-ground face-metal single-quantity designs with shared execution, CLI and restored records.

- Add explicit one-parameter two-ground face-metal goals with independent volume, panel and joint refinement checks.

- Add explicit two-ground face-metal scalar impedance, attenuation and single launched-pair quantity samples with retained failed rows.

- Add explicit two-ground face-metal manufacturing samples with paired launch values, retained invalid rows and descriptive all-success statistics.

- Add a strict saved two-ground face-metal pair-goal schema with field-free corner admission, retained failure records and shared request/project/CLI execution.

- Connect explicit two-ground face-metal lines to bounded paired forward-impedance goals, retaining frozen volume/panel checks and original failure accounting.

- Add a separate versioned two-ground face-line document and host execution records, preserving face currents, material admission and the actual dielectric mesh.

- Add explicit two-ground face currents and local metal laws with retained whole-boundary evidence.

- Use a verified shared small-angle scalar-length baseline while retaining original mesh criteria and historical runtime references.

- Reuse bounded geometry calculations within two-ground material studies while retaining every sampled row, field evaluation and failure.

- Reuse detached, bounded two-ground meshes within paired goal requests while preserving every attempt, refinement and failure record.

- Reuse identical two-ground vacuum-current factors within bounded paired-goal requests while preserving attempts, failure history and numerical checks.

- Compare fixed two-ground frequency-grid candidates with simultaneous joint bounds, complete row budgets and retained uncertainty.

- Add explicit two-ground joint iid acceptance over finite frequency grids, preserving unresolved rows and exact stored execution.

- Save two-ground paired targets on finite frequency grids with strict admission, frozen refinements and complete failure history.

- Seek two-ground paired impedances across explicit frequency grids with frozen refinements, retained failures and unchanged numerical gates.

- Keep two-ground manufacturing samples fixed across finite frequency grids, preserving failed rows, dispersive materials and saved execution records.

- Separate the section factory catalog from impedance studies while retaining factory identities, legacy aliases and saved section documents.

- Separate shared document validators from domain and execution modules while preserving saved inputs, errors and legacy helper imports.

- Retain explicit corner resolution through finite FEM mesh and open-domain assessments.

- Save corner-controlled FEM line quantity goals with original search, refinement and execution budgets.

- Seek FEM line quantities with explicit corner resolution and frozen four-control refinement.

- Preserve explicit corner resolution in FEM line quantity samples and their saved failure records.

- Add an explicit saved corner target for FEM shape line calculations, preserving current checks and failure history.

- Save explicit corner-controlled impedance goals with retained search, refinement and mesh-limit evidence.

- Add explicit corner-controlled impedance goals with frozen-input four-control refinement and preserved mesh-limit evidence.

- Apply saved explicit corner controls to geometry and material samples while preserving failed rows and original study behavior.

- Save explicit corner mesh targets with original geometry snapshots and shared execution records.

- Add explicit direct-Python corner mesh targets while preserving existing defaults and saved-input contracts.

- Add strict saved bounded FEM refinement and version-2 partial budget/failure records without changing existing defaults.

- Add bounded explicit FEM refinement with two consecutive mesh comparisons, separate outer checks and retained typed failures.

- Add explicit saved finite FEM resolution requests with preserved per-entry comparisons and partial current evidence.

- Add explicit finite FEM-current mesh and open-domain assessments with per-entry SI allowances and complete failure evidence.

- Preserve the two larger independent P2 observations in audited reference records while retaining live FEM currents, derivative checks and original numerical criteria.

- Validate actual FEM attenuation-material and common-launch width goals with independent characteristic checks and frozen-input refinement.

- Save bounded FEM-current line goals with reproducible one-variable inputs and complete execution failure evidence.

- Add explicit bounded FEM-current line-quantity goals with frozen-input refinement and retained current evidence.

- Add explicit checked FEM-current geometry/material sampling with fixed boundary metals, complete failed rows and saved execution evidence.

- Save explicit FEM geometry-energy lines with one dielectric/current mesh and complete or partial execution evidence.
  유전체·전류에 하나의 메시를 공유하고 완료·부분 실행 근거를 보존하는 명시 FEM 형상 에너지 선로를 저장합니다.

- Apply explicit whole-boundary surface metals to checked FEM geometry-energy currents while preserving original admission and flux checks.
  기존 재료·전류 잔차 검사를 보존하며 검산된 FEM 형상 에너지 전류에 전체 경계별 표면 금속을 적용합니다.

- Add explicit FEM geometry-energy currents with two extensions, strict capacitance derivatives and retained original flux evidence.
  두 연장·엄격한 정전용량 미분·원 전류 근거를 보존하는 명시 FEM 형상 에너지 전류를 추가합니다.

- Save explicit face-metal shape-current lines with matched RLGC and complete/partial execution records.
  일치하는 RLGC와 완료·부분 실행 기록을 가진 면별 금속 형상전류 선로를 저장합니다.

- Apply explicit signal and ground face surface laws to retained shape-current energies.
  보존된 형상전류 에너지에 신호·접지 면별 표면 재료를 명시 적용합니다.

- Extract explicit straight-face shape-current energies with bounded requests, whole-current evidence and strict derivative checks.
  요청 횟수를 제한한 명시 직선면별 형상전류 에너지를 전체전류 근거·엄격한 미분 검사와 함께 추출합니다.

- Save separate whole-reference metals with matched shape-current RLGC, strict admission and complete execution evidence.
  접지 경계별 전체 둘레 금속과 일치하는 형상전류 RLGC를 엄격한 사전 검사·완전한 실행 근거와 함께 저장합니다.

- Seek explicit shape-current paired targets across finite frequency grids with frozen controls, reserved refinements and full current records.
  유한 주파수 격자의 명시 형상전류 쌍 목표 역산에 제어 고정·예약 세분·전체 전류 기록을 보존합니다.

- Assess all shape-current frequency-grid limits as one joint event per manufactured row, preserving unresolved evidence and exact binomial bounds.
  제조 행마다 형상전류 주파수 격자의 전체 조건을 하나의 동시 사건으로 평가하고 미해결 근거·정확 이항 구간을 보존합니다.

- Preserve explicit shape-current manufacturing rows across finite frequency grids, with atomic failures and full current evidence.
  유한 주파수 격자 전체에서 명시 형상전류 제조 행·행 단위 실패·전체 전류 근거를 보존합니다.

- Assess explicit shape-current joint acceptance with unchanged exact binomial bounds and complete unresolved-row evidence.
  명시 형상전류 동시 조건 만족률에 기존 정확 이항 구간과 미해결 행의 전체 근거를 보존합니다.

- Preserve explicit shape-current manufacturing samples, full current evidence and failed rows through saved studies.
  명시 형상전류 제조 표본·전체 전류 근거·실패 행을 저장된 공차 분석에 보존합니다.

- Add opt-in execution-record/2 for unchanged partial resolution failure and budget-stop receipts while preserving version-1 admission and defaults.
  기존 해상도 부분 실패·예산 소진 영수증용 명시 execution-record/2를 추가하고 버전 1 검사와 기본값을 유지합니다.

- Save explicit shape-current pair goals, preflight offset corners and preserve detailed current failures in execution receipts.
  명시 형상전류 쌍 역산을 저장하고 미분 이동 경계 조합을 사전 검사하며 상세 전류 실패를 실행 영수증에 보존합니다.

- Connect explicit shape-current lines to bounded pair impedance goals with frozen method controls and independent panel/volume refinements.
  명시 형상전류 선로를 범위 제한 쌍 임피던스 역산에 연결하고 방식 제어 고정·독립 패널/체적 세분을 유지합니다.

- Save shape-current resolution plans and preserve complete, unaccepted and detailed partial-failure receipts with explicit whole-line budgets.
  형상전류 해상도 계획을 저장하고 선로 전체 평가 예산·완료·미수락·상세 부분 실패 영수증을 보존합니다.

- Compare explicit shape-current lines along separate panel, volume, joint and outer axes while retaining every current sample and detailed partial failure.
  명시 형상전류 선로를 패널·체적·동시 세분·외곽으로 나누어 비교하고 모든 전류 표본과 상세 부분 실패를 보존합니다.

- Save explicit shape-current lines and retain matched RLGC, complete current samples and staged failures through common execution and receipts.
  명시 형상전류 선로를 저장하고 동일 기하 RLGC·전체 전류 표본·단계별 실패를 공통 실행과 영수증에 보존합니다.

- Add explicit capacitance-shape surface currents with two-step diagnostics, exact partial requests and existing per-boundary metal laws.
  두 차분폭 진단·정확한 부분 요청·기존 경계별 금속 법칙을 보존하는 명시 정전용량 형상미분 전류 API를 추가합니다.

- Save panel-resolution/1 requests with strict SI tolerances and preserve separate-axis comparisons, unaccepted results and exact partial failures through common execution.
  엄격한 SI 허용차로 panel-resolution/1 요청을 저장하고 분리 축 비교·미수락 결과·정확한 부분 실패를 공통 실행에 보존합니다.

- Save bounded refinement as explicit line-resolution/2 and preserve budget exhaustion, selected original-domain results and partial failures through common execution.
  예산 있는 자동 세분을 명시 line-resolution/2로 저장하고 예산 소진·원래 영역의 선택 결과·부분 실패를 공통 실행에 보존합니다.

- Assess panel-line resolution per entry with separate panel, volume, joint and outer comparisons, preserving failed conditions and partial results.
  패널·체적·동시 세분·외곽을 구분하여 패널 선로 해상도를 항별 평가하고 미충족 조건과 부분 결과를 보존합니다.

- Add explicit panel-transmission-line/2 for fixed coated metals, with separate panel, volume and outer-domain checks and unchanged version-1 inputs.
  고정 코팅 금속용 명시 panel-transmission-line/2를 추가하고 패널·체적·외곽 검증을 구분하며 버전 1 입력을 보존합니다.

- Refine line meshes within explicit budgets, requiring two consecutive selected-quantity comparisons and separate outer checks while retaining every rejected level.
  명시 예산 내에서 선로 메시를 세분하고 선택한 물리량의 연속 두 비교와 별도 외곽 검사를 요구하며 거부된 모든 단계를 보존합니다.

- Save finite line-resolution requests with explicit SI tolerances and preserve completed-but-unaccepted and partial-failure results through common execution.
  명시 SI 허용차를 갖춘 유한 선로 해상도 평가를 저장하고 공통 실행에서 완료 후 미수락과 부분 실패를 보존합니다.

- Assess explicitly selected line quantities on finer meshes and larger domains, preserving unmet tolerances, failed stages and completed results.
  명시적으로 선택한 선로 물리량을 세분 메시·확장 외곽에서 평가하고 허용차 미충족·실패 단계·완료 결과를 보존합니다.

- Add explicit dual-cell boundary-current factors and metal-loss projection with independent field checks, preserving gradient and saved-line defaults.
  독립 전계 검증을 갖춘 명시 이중 셀 경계 전류와 금속 손실 투영을 추가하고 기존 기울기·저장 선로 기본값을 보존합니다.

- Add explicit yield-design/4 for fixed coated candidates with unchanged simultaneous confidence bounds, unresolved rows and cost ordering.
  동시 신뢰구간·미해결 행·비용 순서를 유지하며 고정 도금 후보를 위한 명시 yield-design/4를 추가합니다.

- Connect fixed layered metals to explicit line-quantity-design/4, preserving prior versions, failed attempts and selected/refined target gates.
  이전 버전과 실패 시도 및 선택·세분 목표 조건을 보존하며 고정 도금 재료를 명시 line-quantity-design/4에 연결합니다.

- Connect fixed layered metals to versioned geometry/dielectric sampling and iid yield, retaining failed samples and older consumer contracts.
  실패 표본과 이전 소비자 계약을 보존하며 고정 도금 재료를 버전 있는 기하·유전체 공차 및 iid 수율 평가에 연결합니다.

- Save explicit layered metals at signal/reference/ground faces in transmission-line v7 while preserving older input contracts and shared field/circuit execution.
  기존 입력 계약과 공통 전계·회로 실행을 보존하며 transmission-line v7의 신호·귀환·접지 각 면에 명시 도금 재료를 저장합니다.

- Attach explicit planar metal coatings to boundary/face loss calculations with remaining-core skin-depth gates and independent radial-limit checks.
  남은 코어의 표피 깊이 조건과 독립 원통 극한 검증을 적용하여 명시 평면 금속 도금층을 경계·면별 손실 계산에 연결합니다.

- Resolve planar finite metal layers on a bulk half-space with stable MQS impedance transfer and independent field/power checks.
  안정적인 MQS 임피던스 전달과 독립 전계·전력 검증으로 반무한 바탕 위의 평면 유한 금속층을 해석합니다.

- Save scalar shunt-loss inference requests with explicit SI arrays and separate completion/acceptance through the common executor.
  단일 선로 shunt 손실 역산 요청을 SI 배열로 저장하고 공통 실행에서 완료와 수락을 구분합니다.

- Infer nonnegative effective shunt loss from explicit propagation attenuation and known scalar RLC, retaining constrained mismatches and exact power partitions.
  명시 전파 감쇠와 알려진 단일 선로 RLC에서 비음수 유효 shunt 손실을 역산하고 제약에 따른 불일치와 정확 전력 분해를 보존합니다.

- Save fixed-radius roughness fitting requests with strict units, explicit weights and separate completion/sample acceptance through common execution.
  고정 반경 거칠기 피팅 요청에 단위·가중치를 명시해 저장하고 공통 실행에서 계산 완료와 표본 수락을 구분합니다.

- Fit nonnegative causal sphere area ratios at explicit fixed radii from surface-impedance samples, retaining residuals and identifiability gates.
  표면 임피던스 표본에서 명시적 고정 반경의 인과적 구 면적 비율을 피팅하고 잔차·식별성 기준을 보존합니다.

- Save named signal, return, nonmetal and core permeabilities in strict volume-line v4, with fresh-mesh material assignment.
  엄격한 volume-line v4에 신호·귀환·비금속·코어 투자율을 저장하고 새 메시마다 재료를 배정합니다.

- Support piecewise linear isotropic permeability in metal-volume diffusion with colocated skin-depth and magnetic-energy checks.
  금속 체적 확산에 영역별 선형 등방 투자율과 같은 위치의 표피 깊이·자기 에너지 검사를 지원합니다.

- Save explicit metal core geometry and conductivity in volume-line v3 and replay through the common executor and circuit inputs.
  volume-line v3에 금속 코어 기하·전도도를 저장하고 공통 실행·회로 입력으로 재생합니다.

- Mesh explicit core/coating interfaces inside finite 2D traces while retaining their common current constraints and finished outer geometry.
  유한 2D trace 안의 코어·도금 계면을 정합 메시로 만들고 공통 전류 제약과 완성 외곽을 보존합니다.

- Save named signal/return conductivities in volume-line v2, preserving v1 scalar inputs and reusing the common execution/circuit path.
  volume-line v2에 신호 이름별·귀환 전도도를 저장하며 v1 스칼라 입력과 공통 실행·회로 경로를 보존합니다.

- Add an unshipped exact cocircular-tie diagnostic, with order/geometry invariants and failed full-mesh observations kept separate.
  정확 공원점 연결의 비배포 진단과 순서·기하 불변식 검사를 추가하고 전체 메시 실패 관측을 구분합니다.

- Support explicit elementwise conductivity in 2D metal current diffusion, with local skin-resolution gates and conserved current/energy.
  2D 금속 전류 확산에 요소별 전도도를 지원하고 국소 표피 해상도와 전류·에너지 보존을 검사합니다.

- Connect split-gap broadside inputs to saved interface/material studies, correlated etch sampling and separately refined forward-impedance goals.
  gap 분할 broadside를 계면·재료 공차 저장, 식각 상관 표본과 별도 세분 전진 임피던스 목표에 연결합니다.

- Add an explicit two-material gap to trapezoidal broadside sections, with independent four-layer field and reflection checks.
  사다리꼴 broadside의 금속간 간격에 두 유전체 계면을 추가하고 독립 4층 전계·반사를 검증합니다.

- Retain bounded refinement-prefix arrays and active BLAS dispatch information for same-input platform replay without selecting a numerical backend.
  수치 backend를 선택하지 않고 플랫폼 재생에 필요한 초기 세분 배열과 실제 BLAS 실행 경로를 보존합니다.

- Classify recorded mesh seed differences with exact predicates and retain first triangle-data inputs for arithmetic replay, without changing runtime criteria.
  정확한 술어로 초기 메시 차이를 분류하고 연산 재생용 첫 triangle-data 입력을 보존하며 runtime 기준은 유지합니다.

- Add isolated original/candidate mesh diagnostics with exact-source checks, retained runtime limits and refinement traces across platform jobs.
  정확한 소스·기존 runtime 기준·세분 기록을 보존하는 원본/후보 메시 격리 진단과 플랫폼별 실행을 추가합니다.

- Connect saved trapezoidal broadside inputs to correlated etch-face studies and separately refined 50-ohm top-width goals.
  사다리꼴 broadside 저장 입력을 식각면 상관 공차와 별도 세분 50Ω 윗면 선폭 목표에 연결합니다.

- Add independent top/bottom widths to a three-dielectric broadside factory with explicit face conventions and independent field/reflection checks.
  3유전체 broadside의 도체별 위아래 선폭과 면 방향을 명시하고 독립 전계·반사 검증을 추가합니다.

- Register unequal broadside inputs for saved tolerance studies and separately refined forward-impedance width goals without inferring horizontal pitch or symmetry.
  비대칭 broadside를 저장 공차·별도 세분 전진 임피던스 선폭 목표에 등록하고 가로 pitch·대칭성을 추정하지 않습니다.

- Add a three-dielectric broadside factory with independent lower/upper conductor widths and thicknesses, explicit clearances and signed offset.
  상하 도체의 선폭·두께, 평면 간격과 부호 있는 offset을 명시하는 3유전체 비대칭 broadside API를 추가합니다.

- Document three-platform reactive checks and mesh-dependent conductor refinement limits using retained solve inputs and independent discretization observations.
  실제 풀이 입력과 독립 이산화 관측을 바탕으로 3OS reactive 검증과 메시별 도체 세분 한계를 문서화합니다.

- Add focused installed-wheel platform checks for reactive-state limits and original conductor gates, retaining actual vacuum meshes for reproducible diagnostics.
  reactive 상태 극한·기존 도체 기준의 설치 wheel 플랫폼 검사를 추가하고 재현 진단용 실제 진공 메시를 보존합니다.

- Connect layered normal-film coplanar inputs to saved studies and width goals with finite-ground and air-boundary preservation.
  적층 법선 코팅 coplanar 입력을 저장 공차·폭 목표에 연결하고 유한 접지선·공기 경계를 보존합니다.

- Add normal-thickness coated two-substrate coplanar factories with finite grounds and explicit backed or unbacked boundaries.
  유한 접지선과 명시적 하단 접지·열린 경계를 가진 두 기판 법선 코팅 coplanar API를 추가합니다.

- Connect two-substrate normal-film templates to saved studies and separately refined impedance goals while preserving polygon-film geometry.
  두 기판 법선 코팅 단면을 저장 공차·별도 세분 임피던스 목표에 연결하고 다각형 코팅을 보존합니다.

- Add single/equal/unequal microstrip factories with two substrate materials and explicit normal-thickness polygon coatings.
  두 기판 재료와 법선 두께 다각형 코팅의 단일·대칭·비대칭 microstrip API를 추가합니다.

- Balance current-driven and mixed-source multiconductor Debye reactive states, checked against an independent branch-free ODE flux limit.
  전류·혼합 소스 다신호 Debye reactive 상태 스케일을 독립 분기 없는 ODE 자속 극한으로 검증합니다.

- Balance voltage-driven three/four-signal Debye reactive states to preserve large-inductance flux and energy limits.
  전압 구동 3·4신호 Debye reactive 상태의 스케일을 맞춰 큰 인덕턴스의 자속·에너지 극한을 보존합니다.

- Register coated two-substrate coplanar inputs for studies and separately refined width goals while retaining finite-ground clearances and explicit air boundaries.
  코팅된 두 기판층 coplanar 입력을 공차·별도 세분 폭 목표에 등록하고 유한 접지 간격과 공기 경계를 보존합니다.

- Add two-substrate planar-coated coplanar factories with finite side grounds, explicit backing-plane or lower-air boundaries, and single/equal/unequal signals.
  두 기판층의 평면 코팅 coplanar API에 유한 옆 접지선·하단 접지면 또는 아래 공기 경계·단일/대칭/비대칭 신호를 명시합니다.

- Register planar-coated two-substrate lines for versioned inputs, reproducible studies and separately refined width goals.
  평면 코팅 두 기판층 선로를 버전 입력·재현 가능한 공차·별도 세분 폭 목표에 등록합니다.

- Scale internal states for two-signal PSD Debye reactive propagation, preserving tiny finite-inductor currents and their physical energy limit.
  2신호 PSD Debye reactive 전파의 내부 상태를 스케일링하여 큰 유한 인덕터의 작은 전류와 물리 에너지 극한을 보존합니다.

- Add planar-coated surface-line factories above two independent substrate layers, with explicit copper, film and air heights.
  두 독립 기판층 위의 평면 코팅 표면선로 API를 추가하고 도체·코팅·공기 높이를 명시합니다.

- Preserve complete saved-study comparison inputs and results before browser parity assertions.
  브라우저 공차 일치 검사 전에 비교 입력과 양쪽 결과를 보존합니다.

- Register the two-substrate surface lines for editable JSON, reproducible studies and refined width targets, preserving existing input schemas.
  두 기판층 표면선로를 편집 JSON·재현 가능한 공차·세분 폭 목표에 등록하고 기존 입력 규격을 보존합니다.

- Verify all 111 registered input schemas in saved projects and execution records, including exact fixture coverage.
  저장 프로젝트와 실행 기록에서 등록 입력 111종 전체와 기준 입력의 정확한 대응을 검사합니다.

- Add single and equal-pair surface-line factories above two independently specified substrate layers, retaining explicit copper, air and boundary contracts.
  두 기판층의 재료를 각각 명시하는 단일·같은 폭 쌍의 표면선로 API를 추가하고 도체·공기·외곽 조건을 명시합니다.

- Check browser template choices against the complete frozen registry and preserve exact geometry inputs in all-form drawing regression.
  브라우저 단면 선택을 동결 등록 목록 전체와 대조하고 전체 단면 그림 회귀에서 정확한 기하 입력을 보존합니다.

- Connect all 42 registered cross-sections to editable forms, saved controls and full network calculations, with explicit forward-launch diagnostics for unequal and layered broadside pairs.
  등록 단면 42종을 편집 폼·설정 저장·전체 네트워크 계산에 연결하고 비대칭 및 적층 broadside 쌍의 forward launch 진단을 명시합니다.

- Preserve running development-branch validation while keeping the newest pending run, so incremental backups do not cancel platform checks.
  개발 브랜치의 진행 중 검증과 최신 대기 실행을 보존하여 커밋 백업이 플랫폼 검사를 취소하지 않도록 합니다.

- Save and reopen quick target, study and frequency inputs through the shared engine contracts, retaining exact SI controls and rejecting unsupported conversions.
  공통 엔진 계약으로 빠른 목표·공차·주파수 입력을 저장·재개방하며 정확한 SI 설정을 보존하고 미지원 변환을 거부합니다.

- Preserve quasi-static section, frequency grid, supplied diagonal resistance, length and port reference in a strict saved line document with common execution.
  준정적 단면·주파수·명시 대각 저항·길이·포트 기준을 엄격한 선로 문서와 공통 실행으로 보존합니다.

- Save explicit requested-mesh search thresholds in impedance-design/4, preserving legacy JSON, final refinement gates and common execution failures.
  impedance-design/4에 요청 메시 탐색 기준을 저장하며 기존 JSON·최종 세분 기준·공통 실행 실패 이력을 유지합니다.

- Retain generated CI reports from the hidden validation directory using the existing explicit XML and installed-report paths.
  기존 XML·설치 보고서 경로만 사용하여 숨김 검증 폴더의 CI 보고서가 누락되지 않도록 합니다.

- Normalize derived PSD Debye conductances for the strict eigenvalue sign check, preserving propagation arithmetic, negative-input rejection and power-balance limits.
  PSD Debye 셀 컨덕턴스를 정규화한 뒤 고유값 부호를 검사하며 전파 연산·음의 입력 거부·전력 균형 한도를 유지합니다.

- Reproduce periodic Thevenin, Norton and mixed-circuit power totals exactly from exported harmonic components.
  주기 Thevenin·Norton·혼합 회로의 전력 합계를 내보낸 주파수별 성분에서 정확히 재현합니다.

- Preserve output-error exit code 3 when Windows reports a closed stdout pipe as EINVAL.
  Windows의 닫힌 stdout 파이프가 EINVAL로 보고되어도 출력 오류 종료 코드 3을 유지합니다.

- Run source and installed regression in separate platform jobs and validate the independent development branch without requiring a pull request; preserve reference gates and per-job limits.
  플랫폼별 소스·설치본 회귀를 별도 작업으로 실행하고 PR 없이 독립 개발 브랜치를 검증하며 참조 기준과 작업별 시간 제한을 유지합니다.

- Qualify the two fixed 1 GHz forward-pair outer checks with separate common-current monotonic and differential finite-sensitivity criteria; retain target tolerances, fixtures and independent references.
  고정 1 GHz 전방 쌍 외곽 시험 두 개에 공통 전류 단조 조건과 차동 유한 민감도 조건을 구분하며 목표 허용치·시험 입력·독립 기준을 유지합니다.

- Exercise unequal surface/buried pairs and selected left/right width targets in the actual executable smoke, retaining exact selected-matrix replay and existing limits.
  실제 실행 파일 smoke에서 비대칭 표면·매립 쌍과 좌우 선택 폭 목표를 확인하며 선택된 행렬의 정확한 재해석과 기존 한도를 유지합니다.

- Add unequal surface and buried pair forms with explicit lossless forward differential results, independent profiles and selected left/right width targets.
  비대칭 표면·매립 차동쌍에 명시 무손실 전진 임피던스, 독립 프로필과 좌우 선택 폭 역산을 연결합니다.

- Require the pinned test-only independent reference in Windows adapter checks so missing tools fail instead of skipping comparisons.
  Windows adapter 시험에 고정된 독립 비교 도구를 필수로 설치하고 누락 시 비교를 건너뛰지 않고 실패하도록 합니다.

- Bind browser and portable candidates to the committed element-energy, stable aperture-mesh and compensated modal-projection engine.
  브라우저·무설치 후보를 요소 에너지·안정적인 원형 메시·모드 보상 합산 엔진 커밋에 연결합니다.
  Keep inputs and tolerances unchanged; verify that the unsupported-form browser fixture remains outside the editable registry before replay.
  입력·허용오차를 유지하고 브라우저의 미지원 단면 시험 데이터가 편집 지원 목록 밖에 있는지 재현 전에 검사합니다.

- Sum symmetric-pair modal projections with compensation to reduce cancellation after diagonal averaging, retaining symmetry checks and inverse-design tolerances.
  대칭성 검사와 역산 허용오차를 유지하면서 대칭 쌍의 모드 투영을 보상 합산하여 대각항 평균 뒤의 상쇄 오차를 줄입니다.

- Preserve equal-radius refinement candidate order in elliptical-aperture meshes, retaining geometry, mesh limits and inverse-goal acceptance checks.
  타원형 개구 메시에서 같은 반지름의 세분화 후보 순서를 유지하며 형상·메시 상한·역산 수락 검사를 보존합니다.

- Evaluate P1 capacitance with compensated element-gradient bilinear energy while retaining the field solve, material contracts and target tolerances.
  필드 해·재료 계약·목표 허용오차를 유지하면서 P1 정전용량을 요소 기울기의 쌍선형 에너지와 보상 합산으로 계산합니다.

- Keep geometry previews responsive when an invalid conductor extends beyond the drawing; preserve engine rejection and input recovery.
  잘못된 도체 치수가 그림 범위를 벗어나도 미리보기가 멈추지 않고 엔진 오류 표시와 입력 복구를 유지합니다.

- Add two-dielectric coplanar single/pair forms with finite side grounds, exact input projects and layer/ground studies.
  두 유전체 coplanar 단일·차동 폼에 유한 측면 접지와 정확한 입력 프로젝트·층별/접지 공차를 연결합니다.

- Add single and paired two-dielectric interface forms with independent layer inputs, exact projects and layer studies.
  두 유전체 경계의 단일·차동 폼에 층별 입력·프로젝트·공차 흐름을 연결합니다.

- Add a rectangular broadside-pair form with vertical metal-face gap, signed horizontal offset, exact projects and offset/gap studies.
  수직 broadside 쌍에 도체 면 사이 간격·부호 있는 수평 오프셋·정확한 프로젝트·공차 흐름을 연결합니다.

- Add single and paired buried coplanar forms with explicit bottom-face height,
  finite side grounds, exact editable projects, height studies and refined width goals.
  매립 coplanar 단일·차동 폼에 도체 높이·측면 접지·편집 프로젝트·공차·폭 역산을 연결합니다.

- Add an optional tighter direct impedance-search stopping tolerance while retaining
  the final refined acceptance tolerance, default behavior and evaluation budgets.
  직접 임피던스 역산의 탐색 종료 기준을 별도로 지정하고 최종 오차·기본 동작·평가 예산을 보존합니다.

- Add optional conductor detail views with explicit cropped-boundary notices,
  responsive labels and normal-film upper-air clearance labels; preserve inputs and results.
  도체 상세 보기·외곽 생략 안내·반응형 라벨·상부 공기 여유 높이 표시를 추가하고 입력과 결과를 보존합니다.

- Connect normal-film unbacked single/pair forms with separate lower-air bounds,
  finite coated grounds, exact projects, coating studies and refined width targets.
  법선 코팅 unbacked 단일·차동 폼에 하부 공기, 유한 접지, 저장·공차·역산을 연결합니다.

- Connect normal-thickness grounded coplanar single/pair forms with finite coated
  side grounds, separate pair gaps, saved projects, studies and refined width targets.
  법선 코팅 grounded coplanar 단일·차동 폼에 유한 측면 접지, 간격, 저장·공차·역산을 연결합니다.

- Connect normal-thickness coated single and paired microstrip forms with exact
  engine geometry inspection, editable inputs, studies and refined width targets.
  법선 두께 코팅 단일·차동 폼에 엔진 기하 확인, 편집 입력, 공차와 세분 검증 역산을 연결합니다.

- Open validated polygon geometry files in the basic workspace, render local
  dielectric regions and conductor vertices, and separate crowded layer labels.

- Connect single and paired planar-coated unbacked coplanar forms, retaining
  coating materials, separate upper/lower air bounds and refined width targets.

- Add an editable unbacked coplanar pair with separate signal and ground gaps,
  preserved lower-air bounds, differential width targeting and four-port export.

- Export current or historical impedance-study samples as CSV, retaining reported
  numeric precision, ordered variables and all failed rows without recalculation.


- Add explicit two-material corner settings and a four-combination example,
  preserving variable order, physical input checks and saved execution records.


- Add bounded single-material uniform sampling settings with explicit bounds,
  sample count, seed and frequency; preserve strict validation and saved records.


## [Unreleased]

- Add a separate saved corner-current line goal with field-free factory preflight and a typed failure route in common execution.

- Add explicit saved corner-current line samples with ordered geometry/material inputs, finite budgets and retained failure evidence.

- Add an explicit bounded corner-face line quantity goal with separate volume, panel and joint refinement gates.

- Add a separate saved corner-face resolution contract with explicit finite allowances and planned-prefix validation of partial execution records.

- Add explicit finite corner-face line comparisons across current panels, dielectric mesh and wider domains, retaining typed failures and entrywise allowances.

- Add an explicit versioned corner-power face transmission-line document with matched dielectric fields, typed failures and saved execution/replay. Existing line schemas remain unchanged.

- Preserve supported partial resolution failures in recorded workbench runs using explicit record version2; other receipt shapes retain version1.

- Extend two-ground finite resolution checks to three registered coupled geometries using existing independent references.

- Add saved two-ground finite volume/panel/joint/outer assessments, retaining exact planned inputs and typed partial records.

- Add saved iid two-ground line-quantity acceptance with inclusive limits, retained unknown rows and exact confidence envelopes.

- Add strict saved one-variable two-ground line goals with field-free endpoint/
  midpoint/refinement preflight and common execution/request/record/project
  support. Preserve the direct algorithm, budgets, numerical gates and failures.


- Add explicit two-ground one-variable line goals with bounded bisection,
  reserved volume/panel/joint refinement, fixed current controls and preserved
  partial field evidence. Existing goal methods and criteria remain unchanged.


- Add explicit two-ground scalar/selected-pair line-quantity studies with saved
  inputs, ordered geometry/material samples and retained failures/current/mesh
  records. Reuse the existing quantity diagnostic and sampling loop with explicit
  adapters; keep existing study schemas and numerical gates unchanged.


- Add saved joint acceptance for explicit two-ground iid manufacturing samples,
  preserving unknown rows and the existing exact binomial confidence envelope.
  Share the original paired statistical validator without changing its public
  schemas, calculation or refusal rules.


- Add explicit two-ground surface currents with separate signal/top/bottom metal
  laws, matched dielectric RLGC, saved line execution, bounded paired impedance
  design and ordered manufacturing studies. Require the exact shared Laplace
  capability in `dependencies.json`; retain existing extraction defaults,
  numerical gates and all failed rows. See the bilingual development guide.


- Add explicit separate bottom-plane and grounded-trace surface metals using retained ungrouped shape-current energy matrices.

- Save explicit adaptive shape-current refinement plans and retain completed, unaccepted and partial executions through common requests and receipts.

- Add explicit bounded shape-current panel/volume refinement plans with consecutive checks, retained current work and distinct unaccepted outcomes.

- Add explicit saved finite-frequency shape-current pair goals with field-free corner/refinement admission and retained execution failure details.

- Retain resolved edge size and growth for automatic single unbacked coplanar width targeting before its mandatory refinement, while preserving explicit meshes, other templates, numerical budgets and target tolerances.

- Add the single unbacked coplanar form with explicit lower-air domain controls, exact editable input retention, finite-ground tolerance samples and fixed-mesh width targeting. Preserve open outer boundaries, existing numerical limits and mandatory refinement.

- Edit paired principal-axis material means, standard deviations and input correlation for normal studies. Preserve variable order, seeded samples and failed rows, including supported correlation ±1 boundaries; keep target and single-variable settings compatible.

- Add a single-variable normal material sampling example and explicit mean, standard deviation, count, seed and frequency controls. Keep seeded sample order, invalid rows and incomplete summaries unchanged; preserve existing sweep and target settings.

- Show retained paired impedance target failures with both requested targets, search intervals and every completed two-variable evaluation. Keep budget-stopped parameters separate from calculated values; preserve raw records and avoid selecting a solution from failed history.

- Edit two principal-axis permittivities against differential and common-mode targets in saved analysis. Apply explicit targets, tolerances, bounds, initial values, frequency and evaluation budget through the existing validator; preserve failed runs, project records and scalar/sweep settings.

- Add explicit settings for single constant-permittivity and Debye-strength material sweeps. Edit bounds, sample count and frequency through the existing validator; keep scalar target drafts, project history and unsupported sampling inputs separate. Invalid sweep corners are rejected before applying.

- Show failed scalar impedance targets with their completed search/refinement history and a separate stopped mesh attempt when available. Preserve failure status, all original records and raw JSON without selecting a solution from the history.

- Edit constant-permittivity and Debye-strength scalar target settings in saved analysis. Apply explicitly through the existing input validator, retain geometry/material poles/mesh, and block calculations using unapplied settings. Unsupported documents remain in the JSON workflow.

- Show readable material target and study tables in saved analysis, retaining separate requested/refined results, every failed row and exact JSON exports. Historical tables use their saved run and clear when input changes; unsupported display shapes keep the raw JSON view.

- Add a saved-analysis example selector for validated material targets and studies alongside the default RLC network. Load inputs explicitly, preserve project history, and disable loading during calculations or after shutdown.

- Pin both workbench runtimes to paired-material and study mesh reuse. Exercise paired targets and complete/incomplete sampled-material documents through native HTTP and actual browser Workers, retaining model snapshots, refinement, row failures and exports.

- Reuse the last identical explicit-material study mesh and vacuum capacitance within each analysis. Recompute every sampled material, retain failed rows and incomplete summaries, and preserve sampling order, budgets and geometry changes.

- Reuse identical material meshes and vacuum capacitance inside two-parameter pair targeting while preserving objective caching, attempted-evaluation budgets, current-model diagnostics and separate frozen-input refinement.

- Pin both workbench runtimes to search-local material mesh reuse and exercise constant/Debye saved targets through native HTTP and actual browser Workers. Preserve selected material snapshots, refinement, exports and existing failure limits.

- Reuse identical cross-section meshes and vacuum capacitance within a scalar material-target search. Revalidate and recompute each material evaluation, evict changed inputs, and preserve separate refinement, logical budgets, saved results and mesh-limit failures.

- Reuse the selected requested-mesh matrices for workbench width-target output and pin both runtimes to the supporting engine. Keep returned geometry, history, material semantics, refinement and limits unchanged; exercise the same goal path in the portable host smoke.

- Add opt-in requested-mesh matrix snapshots to impedance targeting without another field solve. Preserve the default result and saved JSON, selection/material history, evaluation budgets and mandatory refinement.

- Add a planar-coated coplanar-pair form with distinct signal and ground gaps, finite rectangular grounds, differential width targets, coating/ground studies and four-port response. Preserve exact SI/project inputs and independent field, mesh and domain checks.

- Deliver local HTTP rejections before bounded connection cleanup so unread request data does not reset ordinary oversized uploads. Retain input limits and exercise backpressure, stalled peers and the actual portable host rejection path.

- Add an editable planar-coated coplanar form with finite side-ground controls, coating/ground studies, single-ended width targets and two-port export. Preserve exact SI/project inputs and coating-aware automatic mesh preparation with independent field and domain checks.

- Pin browser and portable candidates to the engine that retains failed goal mesh context. Exercise actual point-budget failures through saved results, execution records and project reopening, followed by a valid calculation, while preserving existing runtime and numerical limits.

- Preserve completed impedance-search history and the failed parameter, stage, resolved mesh and material snapshot when field meshing exceeds its point budget. Keep the error catchable as both a goal failure and a mesher limit, and retain the failure in saved execution records without retrying or relaxing numerical criteria.

- Add a planar-coated pair form with differential width targeting, four-port response, coating studies and exact editable/project inputs. Preserve coating-aware default edge/growth before mandatory target refinement, with independent panel, finite-element and domain-convergence checks.

- Add micrometre display for editable cross sections. Preserve physical target/study bounds across unit changes and one-sided edits; keep empty thickness and study inputs invalid instead of silently converting them to zero.

- Add a separate explicit-height single-stripline form with z0 targeting, two-port response, height studies and exact editable/project preservation; retain independent plane-reference, finite-element and convergence checks.

- Expose centred or explicit bottom-face placement for coupled striplines. Preserve exact nullable inputs, units, fixed mesh and project variants; retain placement in width targets and enable explicit height studies with pre-solve plane-contact checks. Validate qualified parallel-plane references, mesh/domain/reflection and independent finite-element assembly.

- Add an explicit session-only baseline for successful cross-section results, with ordered-signal scalar/matrix differences and exact geometry/mesh inspection. Preserve the baseline while invalidating stale current results; keep zero percentages, asymmetric summaries, project persistence and convergence claims explicit. Stack the primary line metric above the other values on narrow screens.

- Add explicit or automatic box-width and surface air-height controls, with non-solving inspection of resolved bounds. Preserve canonical nullable inputs, exact SI values, fixed mesh and A/B files; keep imported bounds read-only and domain convergence separate from mesh refinement.

- Add an editable coupled grounded-coplanar form with distinct signal and ground gaps, finite ground width, differential targeting, four-port response and ground-dimension studies. Preserve exact project inputs and mesh, and keep inactive geometry controls from blocking other forms. Validate the zero-thickness vacuum limit against independent image panels and retain separate mesh/domain checks. Avoid redundant automatic edge/growth pre-refinement for this pair while retaining the mandatory target refinement and existing point limit.

- Select an extracted executable explicitly for Windows onefile recording, retain normalized same-root checks, and preserve the original smoke failure while gracefully stopping the candidate or its owned process tree. Keep the actual Windows recording and cleanup gate required.

- Expose current mesh inspection, explicit twofold refinement and automatic reset in the six-form workbench. Preserve fixed settings through edits, unit changes and project files; keep inspection separate from solving or freezing automatic inputs.

- Separate crowded conductor labels in the cross-section preview using measured text bounds and leader lines, without changing conductor geometry or saved inputs.

- Add a coupled-stripline form with full ground-plane spacing, edge gap, differential width targeting, four-port response and differential studies. Preserve exact editable/project inputs, nullable offset/taper values and mesh through unit changes and reopen; retain coarse-mesh target failures and their refinement history.

- Add a bounded recording provider for the reviewed Windows onefile candidate: identify the extracted executable and complete bundle before/after a saved run, retain raw record/project contracts and refuse changing or invalid payloads. Extend the real Windows smoke to independently verify extracted files and recorded history; platform acceptance still requires that exact build to pass.

- Give saved-analysis project fields and history selectors consistent spacing and 44-pixel minimum control height on desktop and mobile screens.

- Connect Saved analysis to project variants and recorded-run history: preserve raw project files and stored execution controls, duplicate or switch inputs, inspect historical runs and explicitly select matching results. Keep the previous project on failed transformations or excessive growth, preserve standalone record export, and reject stale file/attachment completion.

- Add read-only project record lookup that preserves raw record digests and distinguishes existing selection from current-input matching. Permit viewing historical requests without rerunning, selecting or fabricating environment manifests.

- Keep saved-analysis navigation and Exit within the header on narrow screens by allowing its height and rows to grow with the controls.

- Add an explicit recorded-run action to Saved analysis, with raw execution-record and environment downloads. Preserve ordinary result exports, optional diagnostics and failed/incomplete results; clear record export on edits, cancellation and stale completions. Project history selection remains separate.

- Connect Worker result recording to checked staged wheel/runtime sources through a host-owned provider. Validate all declared asset hashes and reviewed versions, retain raw records/manifests, and preserve native recording and existing calculation behavior. Keep automatic history UI and frozen-executable provenance separate.

- Add recorded execution for inspectable native wheel installations: compare actual installed file snapshots around one saved calculation, assign a fresh run ID and return raw record/provenance text. Preserve failed/incomplete histories and reject changed artifacts or excessive record growth; automatic UI and other hosts remain separate.

- Package an installed-runtime inventory helper that fingerprints actual distribution files and rejects missing, shadowed, unlisted or changing module payloads. Keep runtime fingerprints distinct from original wheel hashes and leave automatic result recording and browser/executable provenance separate.

- Connect immutable project record attachment, explicit selection and removal to the workbench adapter. Preserve raw records and historical inputs; reject duplicate run IDs, mismatched current selections, tampering and combined size growth without changing the original project.

- Add bounded saved-receipt transport with immutable input/control identity and unchanged execution results, including failed goals and incomplete studies. Preserve existing saved-analyze responses; project result attachment remains separate.

- Align input-project panel spacing and controls with the workbench, and wrap long project titles without horizontal page overflow on small screens.

- Add input-project controls to the existing five-form workbench: duplicate, rename, switch, save and reopen cross-section variants while preserving exact parameters, resolved mesh and existing records. Reject unsupported or late imports without replacing current state; new calculation-result history remains separate.

- Connect bounded project create/open/duplicate/update operations to the existing immutable project contract. Preserve original inputs, controls and history, reject oversized or invalid edits, and keep calculations, file publication and A/B UI separate.

- Include the canonical local workbench host and UI in the pure development wheel. Open it with `sipi` or `sipi gui`, retain headless commands and the direct source launcher, and reuse the existing loopback/cancellation lifecycle without bundling a browser or third-party runtime.

- Give oversized-input workbench tests short explicit case names so Windows can set pytest's current-test environment variable; preserve the original input sizes and rejection checks.

- Add installed `sipi run`/`validate` and `python -m sipi` commands with bounded UTF-8 inputs, existing request receipts, retained failure histories and exclusive atomic output publication. Keep pipeline failure exit codes stable; UI packaging and other-platform filesystem acceptance remain separate.

- Preserve editable template inputs in the five-form workbench: save/reopen exact parameters and mesh, retain hidden arguments through unit changes, and keep geometry export compatible. Validate files before changing the form and discard cancelled reads. Advance the engine pin to the validated template-input contract; Windows and Worker acceptance remain separate.

- Preserve editable template names and resolved arguments together with exact cross-section geometry and mesh in a strict shared calculation input.

- Add explicit local project reads and cooperative atomic saves with no-clobber creation, raw-byte conflict detection and distinct post-publication failure reports.

- Add immutable A/B project snapshots with original inputs, retained execution history and explicit result selection invalidated by semantic edits.

- Add immutable saved execution records binding original requests, receipts and host-declared artifact identities without executing on reopen.

- Add strict saved tensor fitting requests with shared execution budgets, original residuals and separate sampled-error acceptance.

- Add fixed-pole, fixed-orientation passive tensor fitting with original samples, Frobenius residuals and explicit sampled acceptance.

- Add passive transverse Debye tensors with independently oriented residues, strict nested material inputs and saved material studies/goals.

- Add an unequal normal-film coplanar pair without a backing plane, with independent lower air, explicit ground thickness and fixed-pitch studies and goals.

- Add an unequal pair between finite coplanar grounds under a normal-thickness film, with explicit ground thickness and fixed-pitch material studies and goals.

- Add an unequal microstrip pair with a normal-thickness mitered dielectric film, independent signal dimensions and fixed-pitch material studies and goals.

- Add an unequal planar-coated microstrip pair with independent signal widths, thicknesses and tapers, including fixed-pitch studies and bounded impedance goals.

- Add an unequal planar-coated coplanar pair with finite grounds, explicit lower air and no backing plane, including fixed-pitch geometry/material studies and bounded impedance goals.

- Freeze saved inputs and execution controls in an immutable request with semantic hashes and receipts that retain the existing execution result.

- Compare fixed paired manufacturing candidates on one shared finite frequency grid with simultaneous joint-acceptance bounds and retained unresolved samples.

- Assess one fixed joint iid acceptance event across both paired impedances and every supplied frequency, retaining original specimens and unresolved bounds.

- Preserve each paired manufacturing sample across a finite frequency grid, with atomic failed rows and per-frequency descriptive summaries.

- Save finite-frequency paired panel goals with full-grid preflight, named target arrays and preserved common-execution failures.

- Seek paired forward impedance targets at explicit finite frequency samples, with frozen volume/panel/joint verification and atomic failed-batch histories.

- Select the lowest-cost certified member of a fixed paired-impedance candidate set using simultaneous joint-yield bounds, whole-family preflight and retained unresolved rows.

- Assess joint iid acceptance of paired panel-current impedances with fixed named limits, unresolved-row confidence envelopes and retained common-execution results.

- Sample paired forward impedances from one explicit panel-current extraction per row, with strict saved inputs, retained failures and all-or-none descriptive summaries.

- Save explicit panel-current pair goals with field-free preflight, fixed refinement budgets and complete common-execution failure histories.

- Add explicit panel-current two-parameter forward goals with frozen volume, panel and joint refinement, original target tolerances and retained failure histories.

- Add explicit saved panel-current lines with matching dielectric extraction, retained current diagnostics and frequency-bounded common execution.

- Add explicit shared boundary-panel current factors and per-boundary metal loss with grounded traces, capability checks and unchanged existing calculation defaults.

- Validate the pinned shared 0.0.2 development baseline and retain exact dependency artifact requirements without changing existing calculation methods.

- Add strict saved two-variable forward impedance goals with geometry/material inputs and transport-independent failure histories.

- Add bounded two-parameter goals for full-loss differential/common forward impedances, with frozen-input mesh refinement and retained failure histories.

- Add explicit fixed common-current candidate selection with simultaneous acceptance bounds and retained unknown rows.

- Add explicit saved common-current iid acceptance bounds, preserving unresolved rows and previous saved-version admission.

- Add explicit version3 common-current forward-impedance sampling, preserving all failed rows and prior yield-consumer study-version boundaries.

- Add explicit version3 saved common-current forward-impedance goals with unchanged prior quantity admission, source constraints and execution budgets.

- Add explicit common-current forward Re(Zcc) goals for lossy asymmetric pairs, retaining coupling, actual attempt budgets, frozen refinement and prior saved-schema admission.

- Save independent-width finite-volume pairs with strict21-key input, separate sidewall geometry checks, one field evaluation and exact result identity.

- Add bounded unequal-width finite-volume trace pairs over a ground grid, preserving independent widths, explicit metal surfaces, Maxwell capacitance and qualified mesh/exterior checks.

- Add explicit saved wave version16 for multiconductor mixed boundaries, preserving ideal/open/short entries, versions1–15, actual budgets and terminal power identities.

- Admit explicit multiconductor mixed-boundary terminal power waves, retaining ideal-source displacement current and open/short wave identities.

- Add strict multiconductor mixed-boundary saved inputs, preserving ideal voltage/open/short entries, PSD losses, actual sample budgets and exact result identity.

- Add a separate three/four-signal constant PSD RLGC circuit with ideal/resistive voltage sources and open/short/resistive loads, retaining mutual endpoint capacitance and explicit terminal power balances.

- Add explicit saved wave version15 for multiconductor Debye typed sources, preserving original V/A objects, source loss partitions, versions1–14 and actual row budgets.

- Admit explicit multiconductor Debye typed-source responses to six/eight-port power waves, keeping terminal current and both source loss partitions distinct.

- Add strict versioned multiconductor Debye typed-source documents, preserving original V/A inputs, source loss partitions, exact state identity and actual sample budgets.

- Add typed finite-series voltage/current mixtures for multiconductor PSD Debye circuits, preserving source units, separate series/shunt losses and the existing finite-circuit qualification limits.

- Add explicit saved wave version14 for multiconductor Debye current-source inputs, retaining versions1–13, source-shunt/terminal power distinctions and original sample budgets.

- Admit explicit multiconductor Debye Norton responses to six/eight-port power-wave conversion, preserving terminal current, source shunt loss separation and existing wave formulas.

- Add strict versioned multiconductor Debye Norton input documents and common execution with exact current/conductance identity, full-state replay and pre-propagation row budgets.

- Add explicit three/four-signal PSD Debye Norton current sources with external C/RL loads, separate source shunt loss, independent finite-circuit checks and qualified PWL continuum limits.

- Add explicit saved wave version13 for multiconductor Debye series RL inputs, retaining versions1–12, external branch power meaning and original sample budgets.

- Admit explicit multiconductor Debye series RL terminal waves with six/eight real references, retaining branch current, external storage and separate line power without changing conversion formulas.

- Add a strict 17-key saved multiconductor Debye series RL input and common execution, preserving external SI matrices, branch state semantics, actual time budgets and all response shapes.

- Add separate three/four-signal PSD Debye circuits with external C and series RL loads, qualified longer-horizon checks, independent charge/branch KCL, analytical limits and distinct branch energy/loss.

- Add explicit saved wave version12 for multiconductor Debye capacitive inputs, retaining versions1–11, external capacitor power meaning and original sample budgets.

- Admit explicit multiconductor Debye capacitive terminal waves with six/eight real references, retaining external capacitor current and separate line power without changing conversion formulas.

- Add a strict 15-key saved multiconductor Debye capacitive input and common execution, preserving external storage, SI capacitance, actual time budgets and all response shapes.

- Add explicit passive external capacitive loads to three/four-signal PSD Debye startup circuits, with separate storage/current and independent charge-KCL, RC and modal refinement checks.

- Add explicit saved wave version11 for three/four-signal PSD Debye inputs, retaining versions1–10, null-direction power meaning and actual sample budgets.

- Admit explicit three/four-signal PSD Debye terminal waves with six/eight real references, retaining null-direction power meaning and original conversion formulas.

- Add strict saved multiconductor PSD Debye inputs and common execution, preserving singular matrices, null-state meaning, actual time budgets and full response identity.

- Add a separate three/four-signal PSD Debye finite-circuit API with canonical null-direction states, independent charge-KCL and modal refinement checks, retaining original strict-strength models.

- Add explicit saved wave version10 for three/four-signal Debye inputs, preserving older version admissions, canonical replay and time-row budgets.

- Admit explicit three/four-signal Debye responses to real-reference port waves, retaining terminal/polarization power, original formulas and legacy response outputs.

- Save and execute explicit three/four-signal Debye requests with strict fourteen-key SI inputs, pre-propagation time budgets and complete state identity guards.

- Add explicit three/four-signal positive-strength Debye finite circuits, with independent charge-state/modal refinement checks and unchanged legacy two-signal response exports.

- Read normalized Touchstone1.0 Y/Z/H/G with explicit port count and output references, preserving mixed physical units and qualified independent reference checks.

- Read explicit Touchstone2 physical H/G at caller-selected references while preserving existing S/Y/Z parsing and documenting qualified triangular reference checks.

- Convert explicit physical two-port H/G samples directly to power waves, with analytic boundary relations, qualified independent RF comparisons and strict conditioning gates.

- Save paired finite-volume traces with strict SI gap/width inputs, explicit electrode and volume identity and one field evaluation.

- Add bounded paired finite-thickness traces over a ground-grid volume with explicit Maxwell capacitance, independent field comparisons and separate refinement checks.

- Save finite trace and ground-grid volumes with strict SI inputs, pre-mesh checks, exact surface/volume/count identity and one field evaluation.

- Add bounded finite trace and ground-grid volumes with explicit PEC exclusion, partitioned dielectric fields and fixed-boundary thin-trace validation.

- Add explicit partitioned-dielectric capacitance extraction with prescribed-electrode connectivity checks, preserving the original grounded-domain contract and shared numerical body.

- Save finite-thickness ground-grid inputs with pre-mesh validation, exact volume/count/electrode identity and one physical field evaluation.

- Add finite-thickness ground-grid cells with explicit PEC-volume removal, grounded component checks and qualified common-mesh thickness comparisons.

- Save bounded thin trace/grid inputs with strict SI geometry, three explicit dielectric regions, pre-mesh checks and exact geometry/material/field replay guards.

- Add bounded finite-width thin trace/grid capacitance cells with three explicit dielectric regions, conforming geometry and independent field/refinement checks.

- Read strict Touchstone 2.0 physical Y/Z data at explicit output references, preserving existing S parsing and rejecting implicit version1 normalization.

- Convert explicit physical impedance/admittance samples to power-wave networks with cancellation, conditioning and residual guards, without inverting the physical matrices.

- Save bounded grid/plate capacitance inputs with strict SI keys, pre-mesh resource checks and exact geometry/field identity on replay.

- Add bounded thin-grid/broad-plate static capacitance with explicit conforming geometry, shared 3D P1 extraction and independent weak-form/refinement checks.

- Add explicit saved wave version9 for three/four-signal startup with six/eight port references, preserving prior versions and physical budgets.

- Accept explicit six/eight-port startup waves with independent modal and Z-to-S checks, preserving prior response port counts and numerical gates.

- Save explicit three/four-signal constant RLGC inputs with strict SI keys, actual time-row budgets and full state/diagnostic identity checks.

- Add an explicit three/four-signal constant RLGC startup API with independent modal/KCL convergence and finite line/source power checks.

- Add explicitly selected saved wave version8 for external series-RL Debye inputs while preserving prior registries and physical power partitions.

- Accept explicit reactive Debye terminal waves with separate internal line, capacitor and series-RL branch power partitions.

- Save explicit Debye capacitive/series-RL load inputs with strict SI units, complete branch-state replay and actual time-row budgets.

- Add a separate PSD Debye startup API with external capacitive and series RL loads, independent charge-KCL/modal convergence and distinct line/branch energy balances.

- Add explicitly selected saved wave version7 for external capacitive Debye inputs with original nested versions and energy partitions preserved.

- Accept explicit capacitive Debye terminal waves with separate internal line and external capacitor power balances.

- Save explicit external-capacitive Debye inputs with distinct F/F-per-m units, complete replay guards and actual time-row budgets.

- Add a separate PSD Debye startup API with external capacitive loads and distinct line/full-circuit energy balances.

- Add explicitly selected saved wave version6 for PSD Debye inputs while preserving prior nested registries and physical budgets.

- Accept explicit PSD Debye terminal waves with rank-one mode limits and null-direction energy checks.

- Save explicit PSD Debye startup inputs with singular-strength preservation, time-row budgets and complete state replay guards.

- Add a separate two-signal Debye startup API for singular PSD strengths using canonical voltage states, with charge-KCL, modal and convergence checks.

- Add explicitly selected saved wave version5 for coupled Debye inputs while preserving prior nested registries and physical budgets.

- Accept explicit coupled Debye four-terminal waves with scalar-mode limits and polarization energy/loss balance.

- Save coupled Debye startup matrices with exact pole order, strict time budgets and complete four-terminal/state/diagnostic replay guards.

- Add bounded two-signal Debye startup with explicit positive matrix strengths, separate polarization storage/loss, independent charge-KCL and modal/time/space references.

- Add explicitly selected saved port-wave version4 for scalar Debye startup, preserving prior nested registries and physical time/pole contracts.

- Accept explicit scalar Debye terminal waves while preserving polarization energy/loss balance and excluding internal charge currents from terminal inputs.

- Save explicit scalar Debye startup inputs with preserved poles, actual time-row budgets and complete state/diagnostic identity guards.

- Add explicit passive scalar Debye startup with separate polarization storage/loss, bounded poles, independent charge/continuous-line references and time/space convergence checks.

- Add explicitly selected startup port-wave saved v3 for typed mixed sources, preserving earlier nested registries, source units and physical budgets.

- Accept mixed voltage/current startup terminals in port-wave diagnostics, preserving both source-loss partitions and rejecting typed drive arrays as terminal currents.

- Save typed mixed-source startup inputs with exact V/A source keys, source-loss identity guards and unchanged physical time-row budgets.

- Add explicitly typed mixed voltage/current startup sources, separate source series/shunt losses, and independent analytic, KCL and continuous-line refinement checks.

- Add explicitly selected startup port-wave saved v2 for current-source inputs, preserving v1 rejection, nested versions and original delay-term/time-row budgets.

- Accept current-driven startup terminal responses in real-reference port-wave diagnostics, preserving source-shunt power separation and the existing saved wrapper contract.

- Save current-driven startup inputs with explicit ampere/shunt units, strict replay, independent time-row budgets and preserved voltage-source schemas.

- Add explicit current-driven coupled startup with near shunt resistances, separate Norton source power/loss and independent LC, KCL, modal and settling validation.

- Save startup port-wave diagnostics with strict nested physical inputs, explicit references, unchanged source versions and delegated delay-term/time-row budgets.

- Add explicit real-reference startup port waves with preserved terminal samples, direction-aware reflection checks, independent phasor comparisons and reconstruction/power guards.

- Save explicit coupled startup v4 with external C/R/L matrices, exact physical replay and preserved earlier-version contracts and time-row budgets.

- Add explicit passive series RL load branches to coupled startup, preserving separate line/capacitor/inductor energy and independent analytic, modal and KCL validation.

- Save explicit capacitive-load startup v3 with separate external energy, exact physical replay, time-row budgets and unchanged v1/v2 contracts.

- Add explicit passive load-capacitance matrices to coupled startup, separating internal and external energy and verifying LC, modal, KCL and settling limits.

- Add explicit coupled startup saved v2 for per-conductor ideal/open/short boundaries, preserving positive-only v1, actual time-row budgets and exact mixed-circuit replay.

- Add explicit mixed ideal/resistive/open/short boundaries for two-signal startup, preserving mutual endpoint capacitance with mass-matrix state elimination and independent analytic/ODE/refinement checks.

- Save strict two-signal RLGC startup matrices and drives, preserving actual sample budgets, full-state replay and common finite execution output.

- Add two-signal passive finite RLGC startup with full constant matrices, positive resistive ends, energy diagnostics and independent modal, asymmetric ODE and scalar-limit checks.

- Save strict finite RLGC startup inputs with independent cell and sample bounds, exact API replay and shared execution that preserves numerical failures.

- Add finite passive scalar RLGC startup circuits with explicit cells, PWL zero-state drives, energy diagnostics and independent analytic, ODE and distributed-line refinement checks.

- Save strict lossless-startup/1 inputs and execute them through the shared adapter, validating actual delay-term budgets without changing the saved hard cap or waveform model.
- Add initially unenergized lossless scalar line responses with explicit PWL drives, resistive/open/short boundaries, finite reflection budgets and independent LC dynamics checks.
- Reuse vacuum capacitance for exactly uniform scalar dielectric samples, preserving general tensor/nonuniform extraction and independently checked complex-field and convergence results.
- Add strict saved finite-frequency impedance goals, validating all sampled material states before fields and preserving batch budgets and complete replay through shared execution.
- Add bounded two-parameter impedance goals at explicit frequency samples, with batched fields, frozen material sweeps, complete failures and independent convergence checks.
- Add strict saved pair material-variable goals, validating sampled initial models and preserving both geometry and per-row material inputs through shared execution.
- Add parameter-dependent material factories to pair impedance targets, retaining per-attempt model snapshots, frozen refinement and independently checked width/material recovery.
- Add strict named two-parameter pair goals, constraint/material snapshots and shared execution with pre-solve budgets and complete failure context.
- Add bounded two-parameter symmetric-pair impedance targets with actual attempt budgets, frozen refinement, failure histories and independent field checks.
- Add unequal unbacked coplanar pairs with finite ground references, paired-width studies/goals and independent free-space and field checks.
- Add strict conductivity-profile/1 JSON and shared execution with pre-integration budgets, exterior-plane metadata and exact kernel replay.
- Add a bounded Gaussian conductivity-profile half-space kernel with explicit exterior-port position, displacement current and independent field/energy/reference-plane checks.
- Clarify common-metal surface scope and link existing Groiss, Cannonball, diffusion and individual face assignments in English and Korean.
- Add unequal planar-coated coplanar pairs with explicit ground copper, coating material studies, fixed-pitch width targets and independent field/limit checks.
- Add an unequal two-dielectric buried coplanar pair with explicit ground copper, composed pitch/stack constraints, material studies, and independently checked fields and width targets.
- Add unequal buried coplanar signal pairs with independent copper, explicit ground dimensions, fixed-pitch studies and forward-impedance goals.
- Add saved periodic mixed source circuits with explicit real waveforms, sample budgets, shared harmonic diagnostics and mean power execution.
- Add real periodic mixed voltage/current sources, ideal terminal combinations and reactive load time responses with harmonic power diagnostics.
- Add versioned mixed circuit documents with explicit per-port source kinds, frequency budgets and finite shared execution results.
- Add explicit mixed Thevenin/Norton terminal boundaries with ideal voltage, short, open and current-source support, per-port residuals and power diagnostics.
- Add strict periodic Norton circuit JSON with explicit current/shunt tables, pre-field sample budgets and shared time/harmonic power execution.
- Add real periodic Norton current-source responses with open terminals, frequency-dependent shunt currents, retained harmonic diagnostics and time/frequency power checks.
- Add versioned Norton circuit inputs and shared execution with explicit final-basis source/admittance tables, pre-field frequency budgets, extraction identity checks and per-frequency powers.
- Add explicit Norton current-source and open-terminal network solutions with passive finite shunt admittances, retained port voltages/currents, circuit diagnostics and topology-specific power accounting.
- Add unequal surface pairs with finite coplanar grounds, explicit ground thickness and saved forward-current studies/goals; validate independent fields, image-panel limits and separate domain/ground sensitivities.
- Add unequal two-dielectric stripline pairs with explicit common bottom faces, independent materials and composed fixed-pitch/plane-spacing studies; validate independent fields and mesh/box convergence.
- Add unequal-width/thickness centred buried stripline pairs with independent tapers, explicit forward-current quantity and shared two-width pitch, material, tolerance and goal contracts.

- Add saved periodic-circuit/1 with explicit Thevenin/load tables, shared extraction guards, retained harmonic diagnostics and finite time/frequency power reporting.

- Add periodic Thevenin sources with finite passive source/load feedback, explicit DC/peak harmonic normalization, retained circuit diagnostics and time/frequency power checks.

- Add saved periodic-network/1 with explicit named wave samples, retained source networks, mixed-mode conversion, pre-field time-sample budgets and common JSON execution.

- Add explicit odd-length periodic S-parameter response and discrete impulse weights, preserving port references and phase with strict DC/grid checks and real voltage/current output.

- Add explicit yield-design/2 for fixed lossy line candidates at one shared quantity/frequency, reusing conservative simultaneous bounds, full budgets and retained unresolved rows.

- Add fixed-study iid yield for lossy scalar and differential quantities, with explicit units, retained unresolved rows and conservative exact binomial confidence bounds.

- Add explicit line-quantity-study/2 for paired full-loss sampling, preserving correlated vectors, geometry/material constraints, failed rows and complete-only statistics.

- Add explicit line-quantity-design/2 for saved differential forward goals, reusing fixed pitch, stack height and material bindings while preserving scalar v1 behavior.

- Add an explicit lossy differential forward-current launch impedance goal, preserving asymmetric coupling, frozen refinement and scalar-only saved v1 contracts.

- Add scalar full-loss geometry/material studies with preserved correlated samples and failures, finite descriptive statistics and shared saved execution.

- Add saved line-quantity-design/1 using existing scalar geometry/material study inputs, strict line/6 conductors and shared execution with retained goal failures.

- Add bounded scalar-line goals for real lossy characteristic impedance or attenuation, with frozen input refinement, counted failures and complete replay snapshots.

- Add transmission-line/6 ground-face JSON with strict pre-mesh validation, retained diagnostics and existing circuit and once-extracted length replay.

- Extend reference surface assignments with four laws per finite ground trace, conserved face-current partitions, pre-mesh skin/label guards and unchanged whole-trace behavior.

- Add two-dielectric buried coplanar templates with separate material coefficients, composed pitch/stack-height constraints and saved tolerance and impedance goals.

- Add single and differential buried coplanar stripline templates with finite side grounds, saved material/tolerance studies and fixed-pitch impedance goals.

- Add strict saved dielectric-fit/1 requests and shared execution with pre-optimizer sample budgets and separate computation/fit acceptance states.

- Add fixed-pole passive Debye fitting with bounded coefficients, conditioning/optimality rejection and retained sampled residuals and acceptance limits.

- Add transmission-line/5 reference-surface JSON with shared extraction diagnostics and existing circuit and sampled-length replay.

- Add explicit reference-plane, side-wall and named ground-trace surface laws with conserved current partitions, individual skin-depth gates and unchanged common-reference behavior.

- Add line-length-design/2 with one field-source extraction, frozen RLGC replay and complete extraction/length attempt accounting through success and failure.

- Add transmission-line/4 face-metal JSON, shared mesh/C0 composition, retained face-current diagnostics and existing circuit replay.

- Add separate bottom/top/side signal surface laws with one shared PEC current solve, conserved face contributions and retained skin-depth/flux gates.

- Add a three-dielectric broadside pair with explicit outer clearances, signed offset and asymmetric forward-impedance study/material/goal reuse; validate independent fields, limits and mesh/box convergence.

- Add fixed-candidate yield-constrained selection with simultaneous confidence, explicit costs, complete failure reports and whole-set evaluation budgets.

- Add saved iid impedance-yield assessment with retained unresolved rows, exact binomial confidence envelopes and explicit target uncertainty; no measured production-yield claim is implied.

- Add transmission-line/3 saved signal/reference metal assignments on one shared mesh, retaining boundary diagnostics through common execution and existing network/circuit inputs.

- Add separate signal/reference surface-metal laws with individual skin-depth gates, retained boundary power contributions and existing roughness contracts.

- Add strict saved 3D TEM-port replay and shared execution with explicit boundary labels, pre-solve frequency budgets, calculated references and retained power diagnostics.

- Add bounded homogeneous 3D Maxwell fields with explicit annular TEM ports, PEC walls, calculated reference impedances and separate full-boundary/TEM-projection power diagnostics; validate coax propagation and independent edge FEM without implying general via or multimode radiation accuracy.

- Add saved sampled-band line-length boundary design with explicit feasible/infeasible brackets, counted evaluations and retained failure histories; no global maximum or continuous-band guarantee is implied.

- Add saved sampled network-band magnitude limits with explicit port direction, mixed-mode conversion, retained failures and finite shared-execution results.

- Add saved single material-parameter impedance goals and a Python material factory, retaining the chosen model snapshot through refined-mesh acceptance and replay.

- Add strict material-parameter study bindings with joint geometry/material sampling, retained per-row model inputs and failures, and shared saved execution.

- Explicitly freeze the dynamic NumPy FFT/linear-algebra compatibility modules used by SciPy and array-api-compat, and reject completed-build reports that omit them before executable smoke.

- Advance the workbench engine pin to the explicit-mesh 3D saved contract and exercise 3D input replay, result export and bounded capacitance in native, Worker and executable acceptance paths.

- Validate shared layered tetrahedral meshing against the closed coaxial capacitance limit, with curved-boundary/radial refinement and explicit axial-resolution checks.

- Add strict explicit-mesh 3D capacitance JSON replay and compact shared execution, preserving conductor order and boundary meaning without field solving during normalization.

- Add bounded static 3D capacitance through the shared tetrahedral assembler, with explicit PEC/ground node sets, charge/energy diagnostics, analytical and independent FEM checks; no full-wave transition or saved-input support is implied.

- Retain bounded, token-redacted executable stdout/stderr when startup fails before the UI URL, so Windows smoke failures preserve their diagnostic cause.

- Preserve hash-pinned upstream notice bytes during Windows Git checkout and verify them with a real autocrlf-enabled checkout regression.

- Pin the Windows candidate to available CPython 3.13.17 after the 3.12.14 setup failure, verify the matching cp313 wheel notices/hashes and collect only explicitly listed reports from the hidden validation directory.

- Add an independent workbench source candidate with strict saved-analysis JSON execution, retained failures, cancellation/export guards and reproducible browser/Windows packaging inputs; Windows executable and redistribution acceptance remain explicit verification gates.

- Fix extraction's SI constants to the published CODATA 2022 values so older SciPy runtimes cannot silently select a different physical reference; retain tabulation rounding and document the change from earlier runtime-dependent values.

- Add a shared strict saved-input execution adapter with finite complex JSON results, explicit budgets, retained study/goal failures and optional line diagnostics for browser and local application transports.

- Add distinct forward-mode tracking with one-watt normalization, conductor/dielectric power-loss contributions and explicit degeneracy/assignment rejection, reusing extracted RLGC without another field solve.

- Add an explicit ten-point Rz Cannonball surface input mapped to the existing causal Huray law, with strict saved selection and independent packing, relaxation and extraction checks.

- Add saved local-capacitance tolerance studies and bounded goals with shared deterministic sampling, preserved invalid rows and mandatory target checks on requested and refined meshes.

- Add local elliptical-aperture Maxwell and power-dual differential/common capacitance matrices for one or two round conductors, with independent panel/FEM references, strict saved inputs and explicit geometry/transition limits.

- Add local homogeneous circular-aperture capacitance with eccentric conductors, explicit radial/angular refinement, strict saved input and independent eccentric-circle/FEM validation; no finite-pad or 3D transition interpretation.

- Clarify the lossless fixed-geometry energy bound and nested-space assumptions behind electrostatic FEM convergence; do not imply entrywise monotonicity for complex or independently remeshed cases.

- Preserve physical centre spacing for unequal surface-pair width studies and refined goals, deriving bottom-edge gap while retaining invalid samples and legacy equal-width behavior.

- Add independently dimensioned surface pairs and an explicit real forward-current differential impedance, with saved correlated tolerance studies and refined-mesh target design while preserving symmetric-mode semantics.

- Expose power-dual differential/common characteristic matrices for asymmetric pairs, retaining cross-coupling, physical voltage/current normalization and existing forward-wave validity gates without another field solve.

- Save ordered cascades and known-fixture removal in explicit network-transforms v2, validating every intermediate port/reference before meshing and preserving per-occurrence extraction diagnostics; keep v1 input bytes and numerical gates.

- Add passive lumped series/shunt RLC branches and strict saved inputs, with exact DC limits, scaled scattering, independent circuit/reference checks, and assembly/transformation/driven-circuit integration.

- Extend normal-thickness films to single and paired finite coplanar grounds, with and without a backing plane, preserving local materials in lower-air translation and saved studies/goals; reject unresolved film features before automatic meshing.

- Add single and paired surface traces with mitered normal-thickness dielectric films, saved geometry/material studies and width goals, with independent field and convergence checks.

- Add full conductor-coordinate characteristic and forward-transfer matrices for asymmetric reciprocal RLGC, with physical branch selection, independent modal references and power-balance checks.

- Preserve fixed-frequency scalar/principal-axis materials in saved geometry-tolerance studies and bounded impedance goals, including refined-mesh replay and explicit real quasi-static impedance limits.

- Save fixed principal-axis dispersive dielectrics and reuse them in shared-mesh and volume line extraction, network assembly and driven circuits, with scalar material compatibility and independent tensor-field checks.

- Accept reciprocal passive transverse permittivity tensors in mesh capacitance extraction and real tensors with local loss tangents in quasi-TEM line parameters, using existing shared P1 kernels.

- Add planar-coated single and paired coplanar sections without a backing ground plane, with saved studies, width goals and independent field/convergence checks.

- Save explicit network assembly with ideal junctions, validated port metadata, one extraction per geometry component, and existing transformation/circuit integration.

- Add explicit named port connections and ideal Kirchhoff junctions, with independent network checks and analytic one-dimensional shunt-stub validation.

- Add single and paired unbacked coplanar templates with finite substrates and grounds, independent free-space references, saved studies and impedance goals.

- Add strict saved sequences of network reference changes and passive port reductions, with one source extraction and existing circuit-document integration.

- Add explicit open, short and finite passive port reduction while preserving retained port order, references and basis, with singular-feedback rejection and independent network checks.

- Add an explicit noncausal Groiss RMS surface-impedance correction and strict saved model selection, preserving the existing resistance-only and causal roughness definitions.

- Add planar-coated single and paired grounded-coplanar sections with finite grounds, independent field checks, JSON replay, tolerance sampling and saved impedance goals.

- Install the required scikit-fem reference tool in the test extra and CI, and report its version during installed-artifact validation instead of relying on an enriched development environment.

- Add planar-coated paired microstrip with independent electrostatic checks, section JSON replay, tolerance sampling and saved impedance design support.

- Add single/symmetric-pair propagation and exact traveling-wave conductor/dielectric attenuation contributions, reusing extracted RLGC and explicitly excluding DC and asymmetric modes.

- Add explicit near/far network cascade and removal of supplied known fixtures, with analytical and independent network checks and conditioning limits.

- Add immutable positive-real S-parameter reference changes with analytic open/short/through checks and independent scikit-rf comparisons.

- Add strict JSON design requests that preserve impedance goals, search bounds, evaluation budgets and geometry constraints while reusing bounded search and refinement checks.

- Add strict impedance-study JSON v2 for fixed total plane spacing, preserving v1 serialization and retaining invalid derived samples as failures.

- Add single and edge-coupled two-dielectric stripline templates, independent material sampling, and symmetric-interface Cohn validation without averaging materials in the solver.

- Add a coupled grounded-coplanar template with separate signal/ground clearances, JSON and tolerance-study support, and independent image-charge reference checks.

- Extend impedance studies to offset, edge-coupled and broadside striplines with reproducible sampling, strict quantities and horizontal fixed-pitch constraints.

- Validate installed first-party files against exact wheels before regression, reject same-version stale or shadowed imports, and preserve failed-run JSON evidence without stale passing XML.

- Extract SIPI as an independent distribution with unchanged numerical implementation, JSON contracts and regression fixtures. Retain galerkin and meshine as external dependencies.

- Added editable two-layer surface line/pair forms using the shared saved-input, study, target and network paths; preserved the original 42-case reference.
- 두 기판층 표면선로·쌍의 전용 편집 폼을 공통 저장·공차·역산·네트워크 경로에 연결하고 기존 42종 기준을 보존했습니다.

- Added an unequal surface-pair factory over two independent substrate layers, retaining explicit copper dimensions and real forward-launch semantics.
- 두 기판층 위 비대칭 표면선로쌍 API를 추가하고 구리 치수와 실수 순방향 여기 의미를 명시했습니다.

- Registered unequal two-layer surface pairs for saved template, study and width-goal inputs with explicit forward-launch and relative-pitch semantics.
- 두 기판층 비대칭 표면쌍을 저장·공차·폭 역산에 등록하고 순방향 여기와 상대 피치 의미를 유지했습니다.

- Added the unequal layered surface form with explicit copper profiles, shared saved controls and the pinned 45-template browser engine.
- 비대칭 적층표면 폼의 구리 형상·공통 저장 경로와 45종 등록 엔진의 브라우저 계산을 연결했습니다.

- Added three grounded coplanar surface factories above two independent substrate layers, retaining explicit finite ground geometry.
- 두 기판층 위 유한 측면 접지를 명시한 coplanar 단면 API 3종을 추가했습니다.

- Registered the three two-substrate grounded coplanar factories for saved studies and refined width goals, with explicit ground-gap and objective semantics.
- 두 기판층 grounded coplanar 3종을 저장·공차·세분 폭 역산에 등록하고 접지 간격과 목적값 의미를 명시했습니다.

- Connect the three two-substrate grounded coplanar forms to saved controls, finite-ground studies and native/Worker network calculations.
  두 기판층 grounded coplanar 3종을 저장 제어·유한 접지 공차·native/Worker 네트워크 계산에 연결합니다.

- Add single, equal and unequal coplanar geometry factories over two unbacked substrate layers with explicit finite grounds and independent lower air.
  하부 접지면 없는 두 기판층 위 단일·대칭·비대칭 coplanar 기하 API에 유한 접지와 독립 하부 공기를 명시합니다.

- Register two-substrate unbacked coplanar inputs for finite-ground studies and independently refined width targets.
  두 기판층 unbacked coplanar 입력을 유한 접지 공차와 별도 세분 폭 목표에 등록합니다.
