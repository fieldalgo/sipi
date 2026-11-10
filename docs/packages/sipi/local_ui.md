# Installed local workbench

[한국어](../../locales/ko/pages/packages/sipi/local_ui.md)

After installing a validated development SIPI wheel and its matching dependencies,
run `sipi`. The same cross-section workbench opens in your default browser and
calculates on your PC. No source checkout, account, upload or server framework
is required. This is a development candidate, not a PyPI release announcement.

```sh
sipi
```

`sipi gui` is equivalent. For an explicit URL without opening a browser:

```sh
sipi gui --no-browser --port 0
```

Port 0 chooses an available loopback port; an explicit port must be 0..65535.
The URL's session token is required. Use **Exit** in the UI to stop the local
server and its calculation process, or Ctrl+C in the launching terminal.
Closing only the browser tab does not stop the server. Normal shutdown returns
0; startup failures return 1. `--help` and `--version` start no host.
`sipi run` and `sipi validate` remain [headless commands](cli.md).

Choose one of the six existing forms, enter dimensions and materials, calculate,
find a target width or run a parameter study. **Save editable design** keeps the
template inputs and resolved mesh; **Open design** restores those fields.
**Export geometry** retains the existing geometric JSON behavior. **Saved analysis**
uses the common versioned input engine for calculations without dedicated forms.
See the [workbench guide](../../../workbench/README.md) for model limits, failed
rows, cancellation, stale-result behavior and exports. Input projects let you
duplicate/switch cross-section variants and reopen their saved inputs. New result
history is not stored by this screen. Reopened inputs are not a claim of convergence.

The wheel contains the canonical first-party host, adapter and UI assets copied
at build time, with SIPI's license/notice and a dependency-use notice. It does
not include CPython, Pyodide, a browser engine or third-party native binaries;
normal Python dependencies remain separate installed distributions. No package
import starts a server or opens a browser. Source/editable environments without
built UI assets can use `python workbench/desktop/main.py` from the repository.

The local host retains loopback binding, Host/Origin/token checks, spawned jobs,
explicit cancellation and a five-minute job limit. It is not a public web server.
Actual Linux installed-wheel browser acceptance does not establish Windows/macOS
interactive default-browser support. The installation-free Windows single EXE
remains a separate target and does not require users to install Python.
