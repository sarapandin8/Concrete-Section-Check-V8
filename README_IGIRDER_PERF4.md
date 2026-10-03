# IGIRDER.PERF4 — equivalent faster flexure

Precast I-Girder full-span Flexure now reuses the concrete/rebar sweep and PMM query preparation inside each Calculate operation. Every station retains its original Nu; every physical prestress state retains its own strand stress calculation. All 72 × 120 neutral-axis points remain.

Actual `I_Girder_20m.json`, Final Composite, 21 stations: PERF3 **45.832 s** → PERF4 **5.416 s** (8.46× faster). Browser Calculate button **6.405 s**. These are local measurements, not a deployment runtime guarantee.

All result columns at all stations equal PERF3 exactly. All 86,400 PMM points, every metadata field, warnings and info match the solver extracted from the previous full ZIP for five Final Composite and five Construction physical states. Selected regression: 506 tests / 47 modules passed.

Nu is an applied axial demand, not a computational shortcut. Only use Nu = 0 when the external demand and sign convention have been established from the structural model. Prestressing steel remains in internal strain-compatible equilibrium even at Nu = 0. A separate QA-only Nu = 0 run changed Mn by up to 4.09%; it did not modify the source JSON or production results.

Run:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Actual-input UI fixture: `python -m streamlit run qa/igird_dbqa_perf_runtime.py`.

See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_PERF4_2026-10-03.md` and `qa/evidence/igird_perf4/` for provenance, exact comparisons, diagnostics and remaining engineering gates. Debonding QA remains DBQA1; ULS7 and all existing design-scope limitations remain.
