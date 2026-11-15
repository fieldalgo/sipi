# Request-local two-ground mesh reuse

The single-frequency and finite-grid paired goals reuse identical successful
cross-section meshes within one synchronous request. Direct saved line calls
outside a paired goal keep their uncached behavior. No solver, mesh controls,
point limit, target, refinement criterion or evaluation budget changes.

The private key includes the complete canonical cross-section document: geometry,
ordered conductor names, boundaries, dielectric metadata and all mesh controls.
It also retains the identities of the mesh method and its generation/conversion
entry points. Mesh-settings admission still runs before each lookup. Frequency,
metal laws and panel controls belong to other stages; they do not change this
cross-section mesh. Changed volume controls always request another mesh.

A successful mesh is copied into a private snapshot; the initial caller receives
the original and subsequent callers receive detached deep copies. Nodes, element
connectivity, boundary and region metadata, material arrays and signal/ground
node sets are preserved. Caller mutation cannot change the stored snapshot.
Mesh failures are never cached. Cache-copy allocation failure falls back to the
original direct path; an actual mesh failure keeps its original exception.

Each request retains at most two snapshots with at most 64 MiB of total ndarray
payload. Oversized results are used without caching. This is not a limit on
Python metadata, temporary copies, solver memory or process memory. Least
recently used entries are evicted; normal completion, exceptions and interrupts
clear the scope. Nested and concurrent synchronous requests have separate caches.

For the frozen selected coupled-stripline input, tests compare the complete
saved execution, history, current records and mesh records with reuse disabled.
At 2 GHz and separately on the 2/3.5/5 GHz grid, all four attempts remain and
actual mesh generation calls fall from four to two. Volume and joint use the
same refined mesh; nominal and panel use the same nominal mesh. These repeated
inputs are not independent mesh-convergence evidence. The existing independent
physical and refinement tests remain required. No elapsed-time speedup, other
platform, arbitrary-geometry accuracy or release support is implied.

See [current reuse](two_ground_current_reuse.md),
[saved paired goals](two_ground_pair_goal_document.md) and
[finite-grid goals](two_ground_sampled_pair_goal_document.md).

[한국어](../../locales/ko/pages/packages/sipi/two_ground_mesh_reuse.md)

Manufacturing requests also have independent temporary scopes; see [study reuse](two_ground_study_reuse.md).
