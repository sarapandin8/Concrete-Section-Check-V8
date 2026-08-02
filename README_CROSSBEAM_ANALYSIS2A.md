# CROSSBEAM.ANALYSIS2A — Compact Loads Contract and Shear Visual Cleanup

## Baseline

- Starting ZIP: `concrete-section-pro_CROSSBEAM-ANALYSIS2-aci-prestressed-uls-shear.zip`
- Starting SHA-256: `f9e69c372df2f89f85a4e0b3db5aa8a8366bab1c71b5fec1b0c31ac4c366068f`

## Product decision

Keep the Portal Frame Crossbeam workflow compact and commercial-grade. The
Loads page must not ask the engineer to maintain duplicate metadata or repeat
stage/axis declarations that are already fixed by the app workflow.

The Crossbeam Loads workflow now uses fixed internal conventions:

```text
Station = m
P, V2 = kN
T, M3 = kN·m
P = compression positive
V2 = upward positive
T = right-hand positive about increasing station s
M3 = sagging positive
ULS / SLS At Transfer / SLS At Service = fixed upload tabs
```

Legacy Project JSON contract fields remain readable and serializable for
backward compatibility, but they are not exposed, required, or allowed to
silently redefine new imports.

## Loads UI cleanup

Removed from the Crossbeam Loads page:

- FEA Program input;
- FEA Model / Revision input;
- source force-unit selector;
- source moment-unit selector;
- source P/V2/T/M3 sign selectors;
- repeated Transfer / Service declaration controls;
- repeated source-contract cards and declaration panel;
- Crossbeam axis-convention expander;
- duplicate final stage declaration notice.

The page retains only the engineering inputs needed for the section checks:

```text
Active | Station | Check Point | Case / Combination | P | V2 | T | M3 | Note
```

New Excel/CSV imports are interpreted directly in the fixed canonical Crossbeam
units and signs. Table headers and import templates continue to show the units
needed to prepare valid data.

## Shear UI cleanup

- Removed the redundant full-width amber D-region warning above the chart.
- Kept the engineering scope state in the Shear Status card, Governing Gate
  card, amber chart markers, result table, and collapsed calculation audit.
- Removed FEA Program / Model Revision warnings from Shear source and result
  presentation.
- Renamed `Source warnings` to neutral `Source notes` in the Shear workspace.
- Renamed the final expander to `Calculation limitations` and rendered ordinary
  limitations as neutral text rather than yellow warning panels.
- Replaced `RUNTIME STATE = PASS` in Crossbeam ULS with
  `RESULT MODE = ON-DEMAND`; PASS/FAIL/REVIEW remains owned by the selected
  engineering check below.
- Replaced metadata-heavy FEA wording with compact station-force wording.

A yellow warning remains appropriate only for a real actionable state such as a
stale stored result, blocked source, or invalid engineering input.

## Engineering behavior preserved

- No ACI 318-19 Shear equation changed.
- No `Vc`, `Vs`, `phiVn`, D/C, minimum-reinforcement, spacing, or section-limit
  logic changed.
- No ULS Flexure equation changed.
- No SLS equation changed.
- No Prestress Loss or Effective Prestress equation changed.
- No imported station-force row is recombined or modified.
- No Result Summary or Report/QA solver route was added.
- Bridge/Beam, Building Beam/Girder, and Column/Pier/Wall/Pylon UI behavior is
  preserved.

## Files changed

```text
concrete_pmm_pro/ui/loads_page.py
concrete_pmm_pro/ui/analysis_page.py
concrete_pmm_pro/crossbeam/station_force_contract.py
tests/test_crossbeam_analysis2a_compact_loads_shear_cleanup.py
tests/test_crossbeam_loads1a_compact_station_force_import.py
tests/test_crossbeam_loads1b_separate_sls_transfer_service.py
README.md
README_CROSSBEAM_ANALYSIS2A.md
```

## QA

- Compile: `python -m compileall -q app.py concrete_pmm_pro tests`
- ANALYSIS2A + Loads/Shear targeted regression: 47 passed.
- Complete Crossbeam suite: 543 passed, 5 baseline-existing failures.
- Shared Analysis/navigation/Loads and Bridge/Girder ULS regression:
  290 passed, 1 baseline-existing failure.
- The remaining failures are unchanged source-string assertions from older
  Prestress Loss / Result Summary milestones and are outside ANALYSIS2A scope.
- Live Streamlit browser rendering was not available in the sandbox runtime;
  deployed visual QA remains required before final acceptance.

## Repo summary

Simplify Crossbeam Loads to fixed canonical station-force inputs and remove redundant amber Shear warnings while preserving all accepted ACI 318-19 calculations and shared UI standards.
