# Development

SIPI uses externally installed galerkin and meshine packages. For coordinated development,
install their wheels built from the commit in `dependencies.json`, then install this project
with `python -m pip install --no-deps .`. The pinned commit is a development baseline,
not evidence that equivalent packages have been published to PyPI.

Run `python -m pytest -q` for the source suite. Build a wheel and install it in a clean
environment, copy tests outside the checkout and run the same suite there. Include
scikit-rf 2.2.0 for independent network checks. `integration/test_geometry_adapters.py`
checks the versioned geometry contract with the matching simcase reader; run it explicitly.

`provenance.json` identifies every imported file and its original SHA-256. Numerical
implementation and fixtures are unchanged. This extraction does not publish the website,
create a Windows EXE, or establish new platform support. Source history remains available
at the recorded upstream commit; this repository starts with a traceable snapshot.

[한국어](development.ko.md)
