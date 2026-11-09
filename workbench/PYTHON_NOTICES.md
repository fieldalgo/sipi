# Local Python wheel contents

SIPI's Python wheel includes FieldAlgo's local UI and adapter under Apache-2.0.
The complete SIPI LICENSE and NOTICE accompany this text. These first-party UI
files are copied from the same sources used by the source workbench candidate.

The wheel declares its numerical dependencies and does not bundle their code or
binaries. NumPy and SciPy use BSD-3-Clause; Shapely uses BSD-3-Clause; galerkin
and meshine use Apache-2.0. Their separately installed distributions retain their
own license texts and notices, including notices for libraries those publishers
bundle. Consult those distributions for the actual installed versions and terms.

This wheel contains no Python interpreter, Pyodide runtime, browser engine,
third-party font or native binary. The Windows executable and staged browser
runtime have separate inventories and redistribution checks. This text is not
an inventory or attestation of the user's installed runtime.

Sources: https://github.com/fieldalgo/sipi,
https://github.com/fieldalgo/openphysics,
https://numpy.org/doc/stable/license.html,
https://github.com/scipy/scipy/blob/main/LICENSE.txt,
https://github.com/shapely/shapely/blob/main/LICENSE.txt
