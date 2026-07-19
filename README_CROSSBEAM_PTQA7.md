### CROSSBEAM.PTQA7 - Tendon Profile Import Apply Verification Polish

PTQA7 builds on `CROSSBEAM.PTQA6` and adds an import-specific readiness check
so users can see whether imported Tendon Profile rows are complete enough for
Elevation, Cross Section, and 3D review before replacing the active table.

#### What changed

- Adds active-tendon view-coverage helpers that check every active Tendon ID
  has profile rows, at least two points, unique stations, a left anchorage at
  `s = 0`, and a right anchorage at `s = L`.
- Adds a `View coverage` metric card and a `View coverage check` table inside
  the Tendon Profile import preview panel.
- Locks the guarded apply button when view coverage is incomplete, even when
  the uploaded rows can be parsed.
- Extends the import audit record with `View coverage`, `View issues`, and
  `Active tendons checked`.
- Adds friendlier hints for missing active-tendon rows, missing anchorage rows,
  and insufficient profile points.

#### Scope guard

- Applies only to Crossbeam Tendon Profile import preview/apply verification.
- Does not change Tendon System schema, Segment Layout, Section Builder,
  Project JSON export shape, reports, rebar workflows, or any solver.

#### Validation

- `python -m compileall concrete_pmm_pro/crossbeam/tendon.py concrete_pmm_pro/ui/crossbeam_pages.py tests/test_crossbeam_ptqa4_tendon_profile_import_foundation.py`
- `python -m py_compile concrete_pmm_pro/crossbeam/tendon.py concrete_pmm_pro/ui/crossbeam_pages.py tests/test_crossbeam_ptqa4_tendon_profile_import_foundation.py`
- Source sanity checks cover the PTQA7 helper, UI hook, audit field, and test
  markers. Full `pytest` may require the project test/runtime dependencies to
  be installed in the execution environment.
