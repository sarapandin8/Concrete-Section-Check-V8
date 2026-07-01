# SLS.TENSION.DEFAULT1 — Verified Bonded Tension Reinforcement Default

## Scope
Set the guided SLS tensile-limit control default to **Engineer-confirmed bonded auxiliary reinforcement** for all supported section/stage tabs that use the Beam/Girder SLS stress diagram guide.

## Rationale
The previous default, `Model-detected active ordinary rebar at tensile face`, was useful as a screening aid but could be misleading when ordinary rebar is disabled, hidden from the preview, or not yet modeled in the active stage.  The visible stress-limit guide should default to the engineering assumption the user requested: verified bonded tension reinforcement.

## Behavior
- Startup/default guide method: `Engineer-confirmed bonded auxiliary reinforcement`.
- One-time migration promotes legacy `Model-detected active ordinary rebar at tensile face` defaults to the engineer-confirmed condition.
- Explicit non-default user choices such as `Not verified / use conservative preview` and `No bonded reinforcement / no-tension condition` are preserved.
- The Auto option remains available for manual user selection after the migration flag is set.

## Out of scope
No stress equations, material routing, geometry, Pe/debonding, ULS, report, or project-schema calculation logic were changed.
