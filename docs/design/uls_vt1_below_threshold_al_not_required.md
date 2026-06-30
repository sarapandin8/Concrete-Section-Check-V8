### ULS.VT1 — Do Not Require Longitudinal Al When Torsion Is Below Threshold

Refined Beam/Girder torsion and combined shear + torsion status logic for the torsion-below-threshold case.

#### Root cause
The separate torsion check could correctly show `BELOW THRESHOLD`, but the combined V+T gate still called the longitudinal Al review and blocked the result as `DATA REQUIRED` when longitudinal Al was not available. This was over-conservative communication for a below-threshold torsion case.

#### What changed
- Beam/Girder torsion rows now set `Longitudinal status = NOT REQUIRED` when `Threshold status = BELOW THRESHOLD`.
- Beam/Girder torsion rows set `Al req mm2 = 0.0` for below-threshold torsion.
- Combined V+T rows no longer return `DATA REQUIRED` only because longitudinal Al is missing when the source torsion row is below threshold.
- Combined V+T may still report stress/transverse utilization for transparency, but longitudinal Al is not an acceptance blocker unless torsion design is required.
- Updated notes to explain that longitudinal Al is not required when the torsion source row is below threshold.

#### Not changed
- No shear equations.
- No torsion threshold equation.
- No torsion strength equation.
- No combined V+T stress/transverse equations.
- No rebar table schema or reinforcement generation logic.
- No Results dashboard logic, report model, project schema, or save/load contract.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_beam_uls_vt_below_threshold_al_not_required.py tests/test_beam_uls_vt_plot_action_polish.py tests/test_results_ws3_partial_diagram_review.py tests/test_results_ws2_beam_uls_dashboard.py tests/test_analysis_modes.py
```

Targeted tests passed.
