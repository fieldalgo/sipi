# SIPI 후보의 제3자 구성 목록

[English](THIRD_PARTY.md)

확인일 2026-11-07. 정확 pin은 `packaging/requirements-windows.txt`입니다.
독립 SIPI는 `packaging/engine-ref.txt`, galerkin·meshine은 해당 엔진의
`dependencies.json`에 기록한 공유 소스 커밋을 사용합니다. 후보 workflow는
텍스트 보고서만 업로드하고 EXE·브라우저 런타임은 업로드하지 않습니다.
내부 빌드 성공만으로 바이너리 재배포가 허용되는 것은 아닙니다.

추가 기하 의존성은 native **Shapely 2.2.0 / GEOS 3.14.1**,
Worker **Shapely 2.0.7 / GEOS 3.12.1**입니다. Shapely는 BSD-3-Clause,
GEOS는 LGPL-2.1이며 Windows wheel에는 MSVC 고지도 있습니다.
native/static 구성과 소스 제공·재링크 조건 검토는 미완료입니다.
WASM wheel이 빠뜨린 GEOS 3.12.1 원본 COPYING은 supplemental manifest에
출처·해시와 함께 보존했습니다. 고지를 포함한 것만으로 모든 조건을 충족하지는
않으며 바이너리는 내부 검증 입력으로만 사용합니다.

Windows Shapely wheel은 1,791,280바이트·native 6개,
SHA-256 `90895df6542ae039fc6557dec6194e3509e883fbd6f5788e3c3e7a38fe46b257`입니다.
WASM wheel은 832,503바이트·native 5개,
SHA-256 `586daa7290c2d309f9e8d14589d4aa940b1d84502defb3adecc23e17897e476d`입니다.
Windows C API 문자열과 실제 Worker가 보고한 GEOS 버전을 확인했습니다.
현재 recipe metadata만으로 과거 wheel의 전체 빌드 출처를 확정하지 않습니다.
원문: [GEOS 3.12.1 COPYING](https://github.com/libgeos/geos/blob/3.12.1/COPYING).

UI는 자체 JavaScript/CSS와 시스템 폰트·브라우저 API를 사용하며 framework·웹 폰트·
CDN 스크립트·브라우저 엔진을 포함하지 않습니다.

| 구성 | 용도 | 버전·조건·근거 |
|---|---|---|
| SIPI, galerkin, meshine | 실행 엔진 | `packaging/engine-ref.txt`, Apache-2.0; 각 배포물 LICENSE·NOTICE 보존 |
| CPython | 내장 인터프리터 | 3.12.14, PSF/Python 및 포함 구성 조건; 설치된 LICENSE.txt 보존 |
| NumPy | 배열 | 2.5.4, BSD-3-Clause 및 wheel의 구성 라이선스 |
| SciPy | 수치 계산 | 1.18.1, BSD-3-Clause 및 wheel의 구성 라이선스 |
| array-api-compat | 배열 호환 | 1.16.0, MIT |
| Nuitka | 빌드 도구·컴파일 지원 runtime | **2.8.10**, Apache-2.0; 정확 PyPI metadata·sdist LICENSE 확인. 다른 major로 자동 갱신하지 않음 |
| ordered-set | 빌드 전용 | 4.1.0, MIT; wheel에 전문 없음, 동일 버전 sdist MIT-LICENSE 확인, Elia Robyn Lake 2012–2022 |
| zstandard | 빌드 압축 | 0.25.0, BSD-3-Clause; Windows cp312 wheel 고지 확인 |
| pefile | DLL 검사·빌드 전용 | 2024.8.26, MIT; force-dependencies-pefile로 미검토 scanner 다운로드 회피 |
| setuptools, wheel | 빌드 전용 | 80.9.0 / 0.45.1, MIT |
| pytest | 배포하지 않는 검증 | 8.4.2, MIT |
| MSVC | 설치된 compiler·runtime 구성 | Windows runner Visual Studio 2022; 실제 compiler·복사 DLL을 보고서에 기록. 배포 DLL의 재배포 조건 검토 필요 |

Nuitka 2.8.10 sdist SHA-256:
`03e4d0756d8a11cb2627da3a2d9b518c802d031bf4f2c629e0a7b8c773497452`.
onefile runtime의 수정하지 않은 내장 zstd BSD 고지와 Nuitka Apache 고지를 보존합니다.
빌드 전용 inline utility가 모두 실행 구성으로 들어가는 것은 아니므로 실제 컴파일 보고서를 확인합니다.

NumPy/SciPy Windows wheel은 최상위 BSD 외에 OpenBLAS·정적 GCC runtime/libquadmath·
Qhull·Microsoft runtime DLL 등을 포함합니다. 기존 upstream/OpenPhysics 목록은 새 frozen
app의 재배포 의무를 생략할 근거가 아닙니다. GPL runtime exception과 LGPL libquadmath
조건을 혼동하지 않고 정확 wheel 고지와 각 native 파일·정적 구성을 검토합니다.
전체 바이너리가 허용형이라고 주장하지 않습니다.

외부 배포 전에 native/정적 목록 완성, 빠진 고지와 source/relinking 의무 해소, 재배포 조건 검토,
실제 onefile runtime 구성 확인, Windows 10/11 대화형·오프라인 수락 기록이 필요합니다.
현재 CI는 공개 릴리스가 아닌 내부 검증 artifact를 생성합니다. 소스 구현·내부 빌드 검증만으로
출시 수락을 충족했다고 보지 않습니다.

근거: [정확 버전 PyPI JSON](https://pypi.org/pypi/Nuitka/2.8.10/json), 해당 sdist/wheel
라이선스 파일, pin한 OpenPhysics `docs/third-party.md`. Windows 후보에는 Pyodide가
없으며 별도 브라우저 미리보기는 아래 구성을 사용합니다.

## Windows wheel 확인

CPython 3.12 / Windows x64 입력 wheel을 정확 버전의 PyPI 기록에서 받고 게시된
SHA-256과 대조했습니다.

| Wheel | 바이트 | SHA-256 |
|---|---:|---|
| `numpy-2.5.4-cp312-cp312-win_amd64.whl` | 12,573,091 | `a7b1b6353e36a7e50de2973a38d705c88ee93adcf120673cee7f45a4a3fa223a` |
| `scipy-1.18.1-cp312-cp312-win_amd64.whl` | 36,658,278 | `5e4d44984abc0020154ea81b247adeddcc3ac5527b975ff798bd1ba0adc513c2` |

NumPy에는 DLL/PYD 21개가 있으며 OpenBLAS DLL 20,589,056바이트와
`msvcp140` 575,056바이트를 포함합니다. SciPy에는 DLL/PYD 107개가 있으며
OpenBLAS DLL 20,262,912바이트를 포함합니다. 입력 wheel 목록·크기이며 실제 frozen
앱의 전체 구성이나 EXE 크기가 아닙니다.

수집기는 이름에 LICENSE, COPYING, NOTICE가 포함된 파일을 보존합니다. 전체 항목
검사에서 NumPy 20개, SciPy 5개 고지 파일을 확인했습니다. COPYING 완전일치로는
빠졌던 `scipy/spatial/qhull_src/COPYING_QHULL.txt`도 포함합니다. Qhull을 포함한
제품에는 이 전문과 상류 소스 위치 안내가 필요하며 원문에 소스 위치가 있습니다.
wheel의 GCC Runtime Library Exception은 LGPL libquadmath를 포괄하지 않습니다.
Microsoft runtime 재배포 조건·고지도 별도 검토 사항입니다. wheel 고지 수집만으로
정적 구성이나 소스·재링크 의무 검토가 끝나지는 않습니다.

## 브라우저 runtime

| 구성 | 정확 버전·조건 |
|---|---|
| Pyodide | 0.29.5, MPL-2.0, 원본 NPM 파일을 수정 없이 별도 유지; 라이선스·source tag 링크 포함 |
| WebAssembly CPython | 3.13.2, Python/PSF 라이선스·포함 고지를 같은 source tag에서 수집 |
| NumPy WebAssembly wheel | 2.2.5, BSD-3-Clause 및 wheel 구성 고지 |
| SciPy WebAssembly wheel | 1.14.1, BSD-3-Clause 및 wheel 구성 고지; `scipy.libs/libopenblas.so` 포함 |
| array-api-compat | 1.16.0, MIT, 원본 순수 Python wheel |
| SIPI, galerkin, meshine | native와 같은 source pin, 순수 Python wheel, Apache-2.0 |

Pyodide NPM archive SHA-256:
`6749b10ee515a1458ecea36d860c8ce2a48366e85b3f92d749ad1840e4aff181`.
lock은 CPython 3.13.2, ABI 2025_0, emscripten 4.0.9를 명시합니다.
NumPy wheel SHA-256:
`800c98edc0c864dfa49f07005680c699b4b42b84eae1f8cb19d35b3634e7f05c`;
SciPy wheel SHA-256:
`7a60ad5e52acd8d8059f4acc0932d701c3e07723d82e567523dd1a6e0e85ec3e`.
빌드는 고정 runtime lock의 wheel hash를 검증하고 모든 다운로드 파일·wheel native 항목을
`runtime-manifest.json`에 기록합니다. `notices.txt`에는 각 wheel의 읽을 수 있는
LICENSE/COPYING/NOTICE 파일과 정확한 Pyodide·CPython 고지를 모읍니다.
자동 수집은 정적으로 연결된 CPython/Emscripten/Fortran 구성의 전수 감사를 대신하지 않습니다.
전체 구성·재배포 검토가 미완이므로 공개 배포는 포함하지 않습니다. MPL 파일을 수정하거나
우리 UI와 하나의 파일로 합치지 않습니다.

근거: [Pyodide 0.29.5 소스·라이선스](https://github.com/pyodide/pyodide/tree/0.29.5),
[CPython 3.13.2 라이선스](https://github.com/python/cpython/blob/v3.13.2/LICENSE),
archive의 `pyodide-lock.json` 및 정확 wheel 고지.

추가 고지와 SHA-256은 [`packaging/notices/manifest.json`](packaging/notices/manifest.json)에
있으며 빌드 때 hash를 검사합니다. libffi `f08493d`, hiwire `6a1e672`(변경하지 않은
Pyodide runtime 내부 MPL-2.0), Emscripten 4.0.9와 그 안의 musl/libc++/libc++abi/
compiler-rt/MiniLZ4, zlib 1.3.1, bzip2 1.0.6, CPython의 Expat/HACL*/libmpdec,
OpenBLAS 0.3.26과 LAPACK 고지를 보완했습니다. Emscripten은 MIT 선택지를 사용하고
고지 원문의 대안 조건도 보존합니다. array-api-compat wheel에는 라이선스 파일이 없어
정확 1.16.0 sdist의 MIT 고지를 native·browser 모두에 포함합니다.

버전 근거는 Pyodide 0.29.5 `Makefile.envs`·`cpython/Makefile`, Emscripten 4.0.9 port
recipe, [pyodide-recipes 0.29-20260507](https://github.com/pyodide/pyodide-recipes/tree/0.29-20260507)입니다.
후자는 `NOFORTRAN=1` OpenBLAS에 CLAPACK 3.2.1의 libf2c를 연결하며 원본 archive의
SHA-256은 `6dc4c382164beec8aaed8fd2acc36ad24232c406eda6db462bd4c41d5e455fac`입니다.
그 정확한 고지와 wheel에 빠진 나머지 정적 구성은 추가 수집·검토가 필요합니다.
확인한 고지를 미리보기에 포함했지만 출시 목록 전체가 완료된 것은 아닙니다.
