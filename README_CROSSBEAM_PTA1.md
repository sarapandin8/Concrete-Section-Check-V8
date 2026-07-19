### CROSSBEAM.PTA1 - Prestress Force Source Foundation

PTA1 adds a solver-neutral prestress force source audit for Portal Frame
Crossbeam tendons.  The milestone derives each tendon's source jacking force
from the Tendon System and joins that force source to the Tendon Profile
station audit so future loss, SLS, and ULS milestones have a traceable input
handoff.

#### What changed

- Adds `concrete_pmm_pro.crossbeam.tendon_analysis` with:
  - `tendon_force_source_rows()`;
  - `tendon_force_source_summary()`;
  - `tendon_force_trace_rows()`.
- Calculates per tendon:
  - active status;
  - tendon type;
  - jacking end;
  - strand count;
  - area source;
  - `Aps total`;
  - `fpu`;
  - `fpj/fpu`;
  - `fpj`;
  - `Pj`.
- Uses `Pj (kN) = Aps total (mm2) x fpj (MPa) / 1000`.
- Keeps both-end jacking as one tendon force source; it does not double `Pj`.
- Adds a Tendon System `Jacking Force Source Audit (Pj)` table and active total
  `Pj` metric.
- Adds a Tendon Profile jacking-force station trace that joins force source
  rows to each station/profile row and assigned section face.
- Flags invalid or duplicate Tendon IDs as `REVIEW REQUIRED` so total active
  `Pj` is not credited from ambiguous source rows.

#### Scope guard

- This is a source/audit foundation only.
- No prestress-loss calculation was added.
- No friction, wobble, anchorage set, elastic shortening, creep, shrinkage, or
  relaxation calculation was added.
- No SLS stress, ULS strength, anchorage-zone, deviator-force, D-region, or FEA
  export logic was added.
- No Project JSON shape, report generation, rebar workflow, Segment Layout,
  Section Builder, or solver behavior was changed.

#### Validation

- `python -m compileall app.py concrete_pmm_pro`
- `python -m py_compile app.py concrete_pmm_pro/ui/crossbeam_pages.py concrete_pmm_pro/crossbeam/tendon.py concrete_pmm_pro/crossbeam/tendon_persistence.py concrete_pmm_pro/crossbeam/tendon_analysis.py`
- `python -m pytest tests/test_crossbeam_pta1_prestress_force_source.py tests/test_crossbeam_ptqa4_tendon_profile_import_foundation.py`

#### Repo summary

Add Crossbeam PTA1 prestress-force source audit that derives Aps, fpj, and Pj from the Tendon System and traces the source to profile stations without changing solvers.
