# SLS.TENSION.DEFAULT1 — Verified Bonded Tension Reinforcement Default

## Scope
Set the guided SLS tensile-limit control default to **Verified bonded tension reinforcement** for all supported section/stage tabs that use the Beam/Girder SLS stress diagram guide.

## Rationale
The previous default, `Auto from current ordinary rebar layout`, was useful as a screening aid but could be misleading when ordinary rebar is disabled, hidden from the preview, or not yet modeled in the active stage.  The visible stress-limit guide should default to the engineering assumption the user requested: verified bonded tension reinforcement.

## Behavior
- Startup/default guide method: `Verified bonded tension reinforcement`.
- One-time migration promotes legacy `Auto from current ordinary rebar layout` defaults to the verified condition.
- Explicit non-default user choices such as `Not verified / use conservative preview` and `No bonded reinforcement / no-tension condition` are preserved.
- The Auto option remains available for manual user selection after the migration flag is set.

## Out of scope
No stress equations, material routing, geometry, Pe/debonding, ULS, report, or project-schema calculation logic were changed.
