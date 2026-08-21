# IGIRDER.ULS5B — Shear UI Semantic Polish

Baseline: `IGIRDER.ULS5A — Shear QA Closeout`

Scope is presentation-only and follows the accepted `shear(3).pdf` visual QA.

Changes:

- Analysis page header badge changed from `REVIEW` to neutral `ON-DEMAND` so workspace state is not confused with the engineering result status.
- Near-support ordinary load stations excluded from the AASHTO `dv` governing region now display `NON-GOVERNING` in the audit Status column while preserving their underlying strength/detailing calculations for audit.
- Shear PASS recommended action now refers to the `governing shear check` instead of a `preview row`.

Engineering impact:

- No shear equations changed.
- No `epsilon_s`, `beta`, `theta`, `Vc`, `Vs`, `Vn`, or resistance-factor logic changed.
- No governing-section selection logic changed from ULS5A.
- No Flexure, Interface Shear, Torsion, SLS, Project JSON, or result-persistence behavior changed.
