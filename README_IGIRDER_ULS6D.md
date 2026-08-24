# IGIRDER.ULS6D — Torsion Auto-ph / Support-Face / Rebar UI Closeout

## Scope

This milestone closes the remaining standalone Precast I-Girder torsion input-source gaps that were visible in the ULS6C1 Transverse Rebar and Torsion QA screens. It does not certify the final concurrent longitudinal V+T requirement; that remains owned by the later Shear + Torsion milestone.

## 1. Automatic `ph` from the actual closed-hoop geometry

For Precast I-Girder torsion, `ph` is no longer an independent manual value entered for each transverse zone. The app derives the closed-hoop centerline perimeter from the active section geometry and one shared transverse-hoop geometry basis.

Default centerline offset from the concrete outline is:

`closed-hoop centerline offset = clear cover + db / 2`

where `db` is the transverse bar diameter for the station/zone. The hoop topology is common along the member. Therefore changing stirrup spacing changes `At/s` but does not change the hoop topology; changing bar diameter can change the centerline offset and hence the derived `ph` slightly.

The Transverse Rebar workspace displays the derived `ph` as read-only and includes a section preview showing the concrete outline and the derived closed-hoop centerline. The app refuses a collapsed or split inset geometry instead of silently inventing a hoop.

An optional **Advanced / audited hoop geometry override** can lock a project-approved centerline offset. Even with this override, `ph` remains derived from the section geometry; the override is not a direct manual `ph` entry.

## 2. Qualification of the existing provided transverse zones

The existing shear-zone table remains the single physical transverse-reinforcement source. A torsion row does not duplicate bar size, spacing, `fy`, effective legs, or zone limits.

Each provided zone may be qualified for torsion by confirming:

- Use for Torsion
- Closed Loop
- 135° Hook

`At/s` is evaluated from one closed-loop leg area divided by spacing, while the shear workflow continues to use `Av/s` based on its effective leg count.

Automatic `ph` does **not** silently promote an ordinary shear stirrup to a torsion hoop. Above `0.25 φTcr`, a zone still remains `LAYOUT REQUIRED` until the torsion qualification gates are explicitly satisfied.

## 3. Corner longitudinal detailing gate

The corner longitudinal bar/tendon confirmation is not presented as an already-applicable success when no transverse zone has been selected for torsion. Until at least one torsion-qualified zone is requested, the UI reports the corner-detail state as not applicable yet. This is a detailing audit only; longitudinal bars are not classified as separate “flexure bars” and “torsion bars.”

The existing Longitudinal Rebar table remains the single ordinary longitudinal-rebar source for Flexure and the future concurrent Shear + Torsion check.

## 4. Physical support-face torsion stations remain eligible

IGIRDER.ULS6D distinguishes a physical FEA/load station at `x = 0` or `x = L` from a synthetic diagram-boundary row used only to keep plotted traces continuous.

A physical support-face torsion demand is eligible for the torsion threshold check and may govern. The Shear `dv` critical-section exclusion is not applied to Torsion.

If a support station has no usable flexural-analysis input (for example `Mux = 0` and no developed longitudinal steel at that exact end), the app still performs the section-level `Tcr / 0.25 φTcr` screening. It does not manufacture a full General Procedure capacity when the developed longitudinal source needed for that capacity is unavailable.

## 5. Rebar workspace Total As dashboard correction

The Rebar workspace dashboard now computes the displayed active ordinary-rebar area directly from the active source table, including row Count, before relying on downstream materialized bar objects. This fixes the QA condition where the dashboard displayed `Active Bars = 34` but `Total As ≈ 0 mm²` even though the active table contained approximately `10,681 mm²`.

## 6. Torsion calculation route preserved

This milestone does not replace the ULS6 engineering equations. For a station above the AASHTO torsion investigation threshold and with a fully qualified torsion zone, the intended standalone transverse route remains:

`ph → Ao → Veff → εs → β → θ → At/s → Tn → φTn → D/C`

The standalone Torsion page still does not issue a final member PASS above threshold from transverse `φTn` alone. Final solid-section longitudinal acceptance remains the concurrent AASHTO Article 5.7.3.6.3-1 check in Shear + Torsion.

## 7. Result/cache ownership

Current result versions:

- Torsion: `IGIRDER.ULS6D.auto-ph-support-face-closeout`
- Shear + Torsion dependency: `IGIRDER.ULS6D.combined-vt-longitudinal-pending`

Changes to the shared torsion hoop geometry basis or torsion-zone qualification invalidate Torsion and dependent Shear + Torsion results. The accepted standalone Shear, Final Composite Flexure, and Girder–Deck Interface Shear result ownership is not deliberately invalidated by this milestone.

Derived `ph` audit mirrors are not independent engineering inputs in the calculation hash; the section/cover/bar geometry that produces them is the source of truth.

## 8. QA expectation for the next visual review

With no zones selected for torsion, the correct behavior remains `LAYOUT REQUIRED`.

To exercise the full transverse capacity branch in visual QA:

1. Open **Sections → Rebar → Transverse Rebar**.
2. Confirm the closed-hoop clear-cover / geometry basis.
3. Select the relevant zones as **Use for Torsion**.
4. Confirm **Closed Loop** and **135° Hook** for the actually provided detail.
5. Review the automatically calculated `ph` / centerline preview.
6. Recalculate **Analysis → ULS Strength → Torsion**.

The Torsion page should then expose `Veff`, `εs`, `β`, `θ`, `φTn`, D/C, and the `±φTn` chart trace where the remaining engineering sources are available. A transverse pass above threshold remains `REVIEW — COMBINED CHECK REQUIRED` until the concurrent longitudinal V+T milestone is certified.

## Verification note

The release package is compiled and regression-tested after a clean extract. Live Streamlit visual acceptance still requires review of the running app/PDF supplied by the engineer.
