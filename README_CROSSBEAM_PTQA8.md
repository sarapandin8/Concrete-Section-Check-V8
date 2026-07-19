### CROSSBEAM.PTQA8 - Tendon Profile Import Writeback QA

PTQA8 closes the Crossbeam Tendon Profile CSV/XLSX import polish sequence by
adding a post-apply writeback QA trace.  The goal is to prove that an applied
import is no longer just a preview-table value: it is the active Tendon Profile
source consumed by Project JSON metadata, Calculated Audit context, and the
Elevation/Cross Section/3D review context.

#### What changed

- Adds a post-apply writeback QA helper that compares the imported profile
  signature against `CB_PROFILE_ROWS_KEY` and the live
  `crossbeam_tendon_metadata_from_session_state()` Project JSON profile block.
- Checks that Calculated Audit context can be generated from the active
  post-import profile rows.
- Checks that active tendon view coverage still confirms Elevation, Cross
  Section, and 3D context after writeback.
- Adds `Last import writeback QA` below the last import audit so the user can
  inspect pass/review rows after apply.
- Extends the import audit record with `Writeback QA`, `Writeback issues`,
  `Project JSON rows`, and `Calculated audit rows`.
- Marks the writeback QA summary as `UNDONE` when the last import is undone.

#### Scope guard

- Applies only to Crossbeam Tendon Profile import apply/writeback QA.
- Does not change Project JSON shape, report generation, Tendon System schema,
  Segment Layout, Section Builder, rebar workflows, or any solver.
- This is the intended closeout for the CSV/XLSX Tendon Profile import polish
  sequence before moving to the next major Crossbeam milestone.

#### Validation

- `python -m compileall concrete_pmm_pro/crossbeam/tendon.py concrete_pmm_pro/ui/crossbeam_pages.py tests/test_crossbeam_ptqa4_tendon_profile_import_foundation.py`
- `python -m py_compile concrete_pmm_pro/crossbeam/tendon.py concrete_pmm_pro/ui/crossbeam_pages.py tests/test_crossbeam_ptqa4_tendon_profile_import_foundation.py`
- Source sanity checks cover the PTQA8 writeback helper, Project JSON metadata
  comparison hook, UI expander, audit fields, and regression-test markers.
