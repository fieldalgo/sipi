# SIPI candidate dependency inventory

[한국어](THIRD_PARTY.ko.md)

Exact pins are in `packaging/requirements-windows.txt`. Check date: 2026-11-07.
SIPI is pinned by `packaging/engine-ref.txt` in the independent repository;
galerkin/meshine use that commit's `dependencies.json` shared source pin.
The candidate workflow uploads text reports only. It does not upload a frozen
EXE or browser runtime. Internal build success does not authorize redistribution.
The UI is original JavaScript/CSS using system fonts and browser APIs: no UI
framework, web font, CDN script or browser engine is bundled.

| Component | Use | Version / terms / evidence |
|---|---|---|
| SIPI, galerkin, meshine | Runtime engine | `packaging/engine-ref.txt`, Apache-2.0; preserve each distribution's LICENSE and NOTICE |
| CPython | Embedded interpreter | 3.12.14, PSF/Python license and bundled-component terms; preserve installed `LICENSE.txt` |
| NumPy | Runtime arrays | 2.5.4; BSD-3-Clause and component licenses in wheel |
| SciPy | Runtime numerical routines | 1.18.1; BSD-3-Clause and component licenses in wheel |
| Shapely | Geometry operations | 2.2.0; BSD-3-Clause, bundled GEOS 3.14.1 under LGPL-2.1 and Microsoft runtime notice; closure/relinking review incomplete |
| array-api-compat | Runtime array compatibility | 1.16.0, MIT |
| Nuitka | Build tool and compiled support runtime | **2.8.10**, Apache-2.0; PyPI version metadata and sdist `LICENSE.txt` checked. Do not float to another major version |
| ordered-set | Build-only | 4.1.0, MIT; wheel lacks license text, confirmed in identical-version sdist `MIT-LICENSE`, Elia Robyn Lake 2012–2022 |
| zstandard | Build compression | 0.25.0, BSD-3-Clause; Windows cp312 wheel license checked |
| pefile | Build-only DLL inspection | 2024.8.26, MIT; used with Nuitka's `force-dependencies-pefile` option to avoid an unreviewed dependency-scanner download |
| setuptools, wheel | Build-only | 80.9.0 / 0.45.1, MIT; engine build infrastructure |
| pytest | Unshipped verification | 8.4.2, MIT |
| MSVC | Installed compiler and runtime components | Visual Studio 2022 on Windows runner; record actual compiler and copied runtime DLLs in compilation report. Redistribution terms require review for delivered DLLs |

Nuitka 2.8.10 sdist SHA-256:
`03e4d0756d8a11cb2627da3a2d9b518c802d031bf4f2c629e0a7b8c773497452`.
The onefile runtime's bundled zstd is unmodified; retain its BSD notice as well
as Nuitka's Apache notice. Other build-only inline utilities do not automatically
become shipped runtime components; inspect the actual compilation report.

NumPy/SciPy Windows wheels carry native components beyond their top-level BSD
licenses, including OpenBLAS, static GCC runtime/libquadmath, Qhull and Microsoft
runtime DLLs. Their existing upstream/OpenPhysics inventory is an input to this
review, not evidence that a new frozen application can omit notices or binary
redistribution obligations. In particular, GPL runtime exceptions and LGPL
libquadmath terms must not be conflated. Preserve the exact wheel notices and
inspect each bundled native file and statically linked component. No blanket
claim that the binary bundle is all-permissive is made.

Before external distribution, complete the native/static inventory, resolve
missing upstream notices and applicable source/relinking obligations, review
redistribution terms, check the actual onefile runtime closure, and record
Windows 10/11 interactive/offline acceptance. The current workflow creates
internal validation artifacts, not a public release. Source UI/API development
and internal build verification do not establish that release acceptance.

Sources: exact-version [PyPI JSON](https://pypi.org/pypi/Nuitka/2.8.10/json),
the corresponding source/wheel license files, and the pinned OpenPhysics
`docs/third-party.md` native-component inventory. The Windows candidate does
not include Pyodide. The separate browser preview uses the inventory below.

## Windows wheel inspection

The exact CPython 3.12 / Windows x64 input wheels were downloaded from their
versioned PyPI records and checked against the published SHA-256 values:

| Wheel | Bytes | SHA-256 |
|---|---:|---|
| `numpy-2.5.4-cp312-cp312-win_amd64.whl` | 12,573,091 | `a7b1b6353e36a7e50de2973a38d705c88ee93adcf120673cee7f45a4a3fa223a` |
| `scipy-1.18.1-cp312-cp312-win_amd64.whl` | 36,658,278 | `5e4d44984abc0020154ea81b247adeddcc3ac5527b975ff798bd1ba0adc513c2` |

NumPy contains 21 DLL/PYD files, including an OpenBLAS DLL (20,589,056 bytes)
and `msvcp140` (575,056 bytes). SciPy contains 107 DLL/PYD files, including an
OpenBLAS DLL (20,262,912 bytes). These are input-wheel inventories and sizes,
not the frozen application's dependency closure or EXE size.

The collector includes names containing LICENSE, COPYING or NOTICE. Inspection
of all members found 20 NumPy and five SciPy notice files. This includes
`scipy/spatial/qhull_src/COPYING_QHULL.txt`, which an exact-name COPYING match
missed. Qhull requires this text and an upstream-source notice with products
containing it; the original notice includes that source location. The wheel's
GCC Runtime Library Exception does not cover LGPL libquadmath. Microsoft runtime
redistribution terms and notices are still separate review items. Collected
wheel notices alone do not close the static-component or source/relinking review.

## Browser runtime

| Component | Exact version and terms |
|---|---|
| Pyodide | 0.29.5, MPL-2.0, original NPM files kept separate and unmodified; license and source-tag link included |
| CPython for WebAssembly | 3.13.2, Python/PSF license and included notices copied from that source tag |
| NumPy WebAssembly wheel | 2.2.5, BSD-3-Clause plus wheel component notices |
| SciPy WebAssembly wheel | 1.14.1, BSD-3-Clause plus wheel component notices; includes `scipy.libs/libopenblas.so` |
| Shapely WebAssembly wheel | 2.0.7, BSD-3-Clause; bundled GEOS 3.12.1, LGPL-2.1; upstream GEOS COPYING retained separately because the wheel omits it |
| array-api-compat | 1.16.0, MIT, original pure Python wheel |
| SIPI, galerkin, meshine | Same pinned source as native; pure Python wheels, Apache-2.0 |

The Pyodide NPM archive SHA-256 is
`6749b10ee515a1458ecea36d860c8ce2a48366e85b3f92d749ad1840e4aff181`.
Its lock specifies CPython 3.13.2, ABI 2025_0, emscripten 4.0.9.
NumPy wheel SHA-256 is
`800c98edc0c864dfa49f07005680c699b4b42b84eae1f8cb19d35b3634e7f05c`;
SciPy wheel SHA-256 is
`7a60ad5e52acd8d8059f4acc0932d701c3e07723d82e567523dd1a6e0e85ec3e`.
The build verifies wheel hashes against the immutable runtime lock and records
all fetched files and native wheel members in `runtime-manifest.json`.
`notices.txt` collects readable LICENSE/COPYING/NOTICE files from each wheel,
the exact Pyodide license and CPython license. This automatic collection is not
a completed audit of statically linked CPython/Emscripten/Fortran components.
No public deployment is included while that closure and redistribution review
remain incomplete. MPL files are neither modified nor concatenated with our UI.

Sources: [Pyodide 0.29.5 source and license](https://github.com/pyodide/pyodide/tree/0.29.5),
[CPython 3.13.2 license](https://github.com/python/cpython/blob/v3.13.2/LICENSE),
the archive's `pyodide-lock.json` and the exact wheel notices.

Supplemental exact-source notices and their SHA-256 values are checked into
[`packaging/notices/manifest.json`](packaging/notices/manifest.json). They cover libffi
`f08493d`, hiwire `6a1e672` (MPL-2.0, within the unchanged Pyodide runtime),
Emscripten 4.0.9 and its musl/libc++/libc++abi/compiler-rt/MiniLZ4 copies,
zlib 1.3.1, bzip2 1.0.6, CPython's Expat/HACL*/libmpdec copies, OpenBLAS 0.3.26
and its LAPACK copy. Emscripten's MIT option is selected; copied license texts
retain their original alternative terms. The native and browser builds also
include array-api-compat's MIT notice from its exact 1.16.0 source distribution,
because that wheel omits the license file.

Source-version evidence is the Pyodide 0.29.5 `Makefile.envs` and
`cpython/Makefile`, Emscripten 4.0.9 port recipes, and
[pyodide-recipes 0.29-20260507](https://github.com/pyodide/pyodide-recipes/tree/0.29-20260507).
The latter links libf2c from CLAPACK 3.2.1 into OpenBLAS with `NOFORTRAN=1`;
its source archive is pinned to SHA-256
`6dc4c382164beec8aaed8fd2acc36ad24232c406eda6db462bd4c41d5e455fac`.
Its exact notice still needs collection, as do any remaining statically bundled
components absent from wheel notices. This is explicitly an incomplete release
inventory, even though the verified supplemental texts are included in previews.

## Geometry wheel inspection

The Windows Shapely 2.2.0 cp312/x64 wheel has SHA-256
`90895df6542ae039fc6557dec6194e3509e883fbd6f5788e3c3e7a38fe46b257`,
1,791,280 bytes and six native files (three PYD, GEOS, GEOS C and MSVC DLLs).
Its GEOS C API string identifies 3.14.1. The wheel contains BSD, LGPL-2.1 and
Windows runtime license texts. The Pyodide Shapely 2.0.7 wheel has SHA-256
`586daa7290c2d309f9e8d14589d4aa940b1d84502defb3adecc23e17897e476d`,
832,503 bytes and five native objects. Actual Worker execution reports GEOS
3.12.1. The original [GEOS 3.12.1 COPYING](https://github.com/libgeos/geos/blob/3.12.1/COPYING)
is included in the supplemental manifest with its source and notice hashes.
Current recipe metadata is not proof of the historical wheel's complete build
provenance. Keeping the license text does not alone satisfy all applicable
source/relinking obligations. These binaries remain internal validation inputs.
