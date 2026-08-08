# CROSSBEAM.ANALYSIS4C7D10 — Combined V+T component traceability closeout

## Scope
Close the remaining Combined V+T presentation/source-of-truth defects found during visual QA of D9 without changing any ACI strength equation.

## Changes
1. Component evidence tables now report the status owned by the selected engineering view:
   - Section-size interaction → `Stress status`
   - Transverse reinforcement → `Transverse status`
   - Longitudinal reinforcement → `Longitudinal status`
   The table header remains `Status`, but it no longer inherits the overall Combined V+T row status.

2. Combined V+T governing-row selection now resolves flat D/C ties deterministically:
   - genuinely larger D/C always governs;
   - for D/C ties within tolerance, imported/actual station > generated support station > generated near-joint station;
   - remaining ties resolve deterministically by station/check point.

For the accepted 30 m Segmental benchmark, the governing Aℓ plateau remains D/C = 2.262128..., but the summary now consistently reports the imported station at s = 6.000 m instead of the generated near-joint station at s = 4.600 m.

## Engineering behavior preserved
- ACI 9.5.4.3 combined transverse reinforcement equation unchanged.
- ACI 9.5.4.4 direct flexure + torsional longitudinal tension unchanged.
- ACI 9.6.4 minimum longitudinal torsion reinforcement unchanged.
- ACI 22.7.7 section-size interaction unchanged.
- Physical-joint V+T transfer remains NOT EVALUATED and audit-only.
- Segmental/CIP construction-type isolation unchanged.

## Verification
- `python -m py_compile app.py concrete_pmm_pro/analysis/crossbeam_uls_combined_vt.py concrete_pmm_pro/ui/analysis_page.py` — PASS
- D10 + D9 + Combined semantics: 16 passed
- Combined solver/decision/component views: 19 passed
- Flexure + Shear + Torsion targeted regression: 39 passed
- D7 Torsion traceability wording: 3 passed
- Total unique targeted tests in these completed groups: 77 passed
