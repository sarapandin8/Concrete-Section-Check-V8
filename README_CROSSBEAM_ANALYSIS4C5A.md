# CROSSBEAM.ANALYSIS4C5A — Active-Mode Geometry Audit and Blocker Contrast

## Scope

This milestone starts from `CROSSBEAM.ANALYSIS4C5` and closes the Project Geometry blocker defect observed while the active Crossbeam construction method is **Cast-in-Place**. It also hardens sidebar blocker contrast and adds direct corrective guidance. No structural solver, load, prestress, reinforcement quantity, or Combined V+T equation is changed.

## Defect reproduced

The active Cast-in-Place Rebar page showed one valid Section/Zone:

```text
Z1 = 0.000–30.000 m
Crossbeam length = 30.000 m
```

but the sidebar still reported:

```text
PROJECT GEOMETRY INCONSISTENT — BLOCKED
```

The audit was reading the dormant **Precast Segmental** Rebar Zone state (`crossbeam_rb1_zone_assignment_rows`) even though the active member used the independent Cast-in-Place assignment source (`crossbeam_rb_cip2a_zone_assignment_rows`). Because the dormant Segment IDs differed from active `Z1`, the audit created a false blocker even though both displayed extents were 0–30 m.

## Correction

### Construction-mode-aware source ownership

The Project Geometry audit now reads only the Rebar assignment source owned by the active construction method:

- `Precast Segmental` → `crossbeam_rb1_zone_assignment_rows`
- `Cast-in-Place` → `crossbeam_rb_cip2a_zone_assignment_rows`

Dormant assignments remain preserved but cannot block the active workflow.

### More accurate geometry diagnostics

When a genuine inconsistency remains, the message now distinguishes:

- active Segment/Zone ID mismatch,
- member-end extent mismatch,
- internal gap/overlap/boundary mismatch,
- unreadable station extent.

It no longer reports equal displayed extents as the reason when the actual problem is an ID or internal-boundary mismatch.

### Readable sidebar blocker

The sidebar blocker now has:

- high-specificity dark-red text overriding the legacy global sidebar white-ink rule,
- stronger border and title hierarchy,
- separate `Reason` and `ACTION` content,
- direct navigation to the page that owns the inconsistent input,
- explicit notice that custom subdivisions are preserved and not overwritten automatically.

## Files changed

- `app.py`
- `concrete_pmm_pro/crossbeam/project_geometry.py`
- `concrete_pmm_pro/ui/crossbeam_project_geometry.py`
- `tests/test_crossbeam_project_json1_restore_authority.py`
- `tests/test_crossbeam_analysis4c5a_geometry_notice.py`
- `README_CROSSBEAM_ANALYSIS4C5A.md`

## Engineering and solver protection

Unchanged from ANALYSIS4C5:

- Crossbeam Direct P–M3 solver
- Shear solver
- Torsion solver
- Combined V+T solver
- Prestress-loss calculations
- Rebar quantity and cage source contracts
- Loads and station-force data
- Project JSON schema and stored engineering values

## QA completed

- Python compileall: PASS
- Active CIP vs dormant Precast geometry-source regression: PASS
- Project JSON geometry authority and reset regression: PASS
- CIP Rebar workflow regression: PASS
- Crossbeam Rebar / Transverse / Project JSON / navigation regression: PASS
- ANALYSIS4C3–4C5 presentation regression: PASS
- Crossbeam Shear / Torsion / Direct Flexure regression: PASS
- Shared commercial sidebar / upload / navigation / theme regression: PASS

No full-repository green claim is made.

## Repo summary

Make Crossbeam Project Geometry auditing construction-mode aware, prevent dormant Precast Rebar Zones from falsely blocking valid Cast-in-Place assignments, and strengthen sidebar blocker contrast with direct corrective guidance.
