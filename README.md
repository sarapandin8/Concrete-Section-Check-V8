# Concrete Section Pro — IGIRDER.FLEXDEP1

Precast I-Girder Construction and Final Composite flexure now include AASHTO LRFD 9th Edition (2020) strand transfer/development, conservative ordinary-bar development, and strain-based φ. The fixed-axis equilibrium solver retains every original Nu. See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_FLEXDEP1_2026-10-04.md` and `docs/CONCRETE_SECTION_PRO_FLEXDEP1_EXPLANATION_2026-10-04.md`.

Run the complete application with `streamlit run app.py`. The dedicated route is selected in Analysis → ULS → Flexure → Construction / Final Composite. Enter physical cut-end extensions and verified development/anchorage declarations, then Calculate each stage. Previous full-strand-strength flexure results are stale.

## Earlier Crossbeam milestone

Eliminates the deployed Crossbeam ULS trace-owner `NameError` by removing the runtime helper lookup and resolving `Zone-owned` versus `Segment-owned` directly at every render site. All ANALYSIS4C7C engineering and chart behavior remains unchanged. See `README_CROSSBEAM_ANALYSIS4C7C2.md`.
