# Touchstone 2.0 물리 Y/Z 입력

[English](../../../../../packages/sipi/touchstone_parameters.md) | **한국어**

`sipi.touchstone`의
`loads_touchstone_parameters(text, *, z_ref, ports=None, port_names=None)`는
single-ended **버전 2.0 Y 또는 Z**의 엄격한 부분집합을
[LineNetwork](network.md)로 읽습니다. 필수 `z_ref`는 출력의 양의 실수 기준저항을
스칼라 또는 포트별 값으로 명시합니다. 기존 [S reader](touchstone.md)의 지원 버전과
파라미터 종류는 그대로 유지하는 별도 API입니다. 엔진은 파일·네트워크 I/O를 하지 않습니다.

```python
from sipi.touchstone import loads_touchstone_parameters

text = """[Version] 2.0
# Hz Z RI R 100
[Number of Ports] 1
[Number of Frequencies] 1
[Reference] 23
[Network Data]
0 200 0
[End]
"""
network = loads_touchstone_parameters(text, z_ref=50., port_names=['terminal'])
assert abs(network.s[0, 0, 0] - (200-50)/(200+50)) < 1e-12
assert network.z_ref[0] == 50.
```

버전 2.0의 Z 숫자는 물리 Ω, Y 숫자는 물리 S(지멘스)입니다. 파일의 `R`과
`[Reference]`는 문법을 검사하지만 이 행렬의 배율이나 출력 기준을 정하지 않습니다.
예제의 행렬은 파일의 100Ω·23Ω와 독립적으로 200Ω이고, 출력은 호출자가 지정한
50Ω 기준입니다. [IBIS Touchstone 2.0 규격 7쪽](https://ibis.org/touchstone_ver2.0/touchstone_ver2_0.pdf)에
정의된 차이입니다. 버전 1.0의 non-S 데이터는 정규화되어 있으므로 **이 API에서는
받지 않습니다**. 버전 이름만 바꾸어 파일을 업그레이드하면 안 됩니다.

```python
# A 40ohm resistor between two terminals has rank-one Y in siemens.
y_text = """[Version] 2.0
# Hz Y RI R 123
[Number of Ports] 2
[Two-Port Data Order] 12_21
[Number of Frequencies] 1
[Network Data]
0 .025 0 -.025 0 -.025 0 .025 0
[End]
"""
series = loads_touchstone_parameters(y_text, z_ref=[50., 50.],
                                     port_names=['left', 'right'])
assert abs(series.s[0, 1, 0] - 100/140) < 1e-12
```

기존 S reader의 엄격한 문법·행렬 해석을 재사용합니다. ASCII, 명시 버전·옵션행,
포트/주파수 개수, network data/end 블록, RI·크기/도 단위 각·dB/도 단위 각,
Hz/kHz/MHz/GHz, full 또는 전치 대칭 lower/upper를 받습니다. 2포트는
21_12 또는 12_21 순서를 반드시 명시하며 더 큰 full 행렬은 행 우선입니다.
`[Reference]`는 여러 줄에 걸쳐도 되지만 존재하면 포트별 양의 실수 값이 하나씩
있어야 합니다. 선택 `ports`는 파일과 일치해야 합니다. 이름은 파일 순서대로
지정하거나 기본 `port1`, `port2`, … 를 사용합니다. 주석·information 블록은
물리 연결을 정하지 않습니다. 결과 배열은 복사한 읽기 전용입니다.

옵션행은 Y 또는 Z를 명시해야 합니다. S/H/G, 기본 S, 버전 1, 혼합모드·노이즈,
알 수 없거나 중복된 키워드, 불완전한 레코드, 비유한 수, `[End]` 뒤 내용은
거부합니다. 기준저항은 양의 실수이며 주파수에 독립적입니다. 보간·외삽·정규화
추정·fixture 제거·수동성 보정은 하지 않습니다.

물리 행렬을 출력 기준과 함께 [impedance_network/admittance_network](parameter_network.md)에
그대로 전달하며 기존 조건수·상쇄·유한성·잔차 기준을 유지합니다. Z나 Y가 특이해도
그 자체의 역행렬 없이 변환할 수 있지만 파동 변환의 분모가 특이하면 거부합니다.
재료·인과성·실측 정확도를 인증하거나 입력 행렬로 선로 모델을 추론하지 않습니다.

`tests/sipi/test_touchstone_parameters.py`는 1–4포트, 형식·단위·비상반 2포트 순서,
삼각 행렬의 전치 대칭, 파일 기준과 독립된 출력 기준, 개방·단락과 저항 해석을
검사합니다. 12가지 버전2 파일을 독립 scikit-rf 2.2.0으로 읽고 출력 기준으로 명시
변환했을 때 절대 S 차이는 1e-12 이하, 주파수는 정확히 같아야 합니다. 기존 S 시험은
변경하지 않았고 parser 분리 전후 110개 기존 S fixture의 출력 바이트를 대조했습니다.
BSD-3-Clause 도구는 시험 전용이며 실행 의존성을 추가하지 않습니다. 파일·대수 단계에는
공간 메시나 외곽 절단이 없고 기존 물리 솔버도 변경하지 않습니다.
