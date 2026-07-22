# CROSSBEAM.PTLOSS3B1 — Construction/Stressing-Stage Source Model

This milestone extends the accepted PTLOSS3A Elastic Shortening foundation with the physical source data required before a future Portal-Frame stressing-stage solver can derive Primary/Secondary Prestress, temporary-support contact response, and source-derived `f_cgp`.

## Construction/stage source

- Construction method: `Precast Segmental` or `Cast-in-Place`.
- Crossbeam stressing-strength criterion defaults to `0.80 f'c` as a project assumption and remains editable/verification-gated.
- Precast Segmental stores separate required and verified joint/closure concrete strengths at stressing.
- The milestone does not hard-code a universal closure strength above the Crossbeam `f'c`; the approved project requirement is an explicit source.

## Column / Portal-Frame source

Column layout is user-defined by station and physical geometry. Column bases are currently fixed by the accepted Crossbeam project assumption.

Supported column shapes aligned to the app local axes:

1. Rectangular with equal chamfers at all four corners.
2. Rectangular with equal fillets at all four corners.
3. Circular.

The user enters physical geometry, height, and `f'c`. The app derives gross `A`, `I22`, `I33`, ACI normal-weight `Ec`, `EA`, and `EI` source values. PTLOSS3B1 does not yet use them in a frame solver.

## Temporary support / falsework source

The accepted default construction idealization is:

- Continuous support over the full Crossbeam length.
- Initially in contact.
- Vertical compression-only contact.
- No tensile/uplift resistance.
- Automatic lift-off required in the future stage solver if a contact point would require tensile reaction.
- Intentional final support removal remains a separate post-stressing stage.

PTLOSS3B1 stores this source definition only. It does not yet perform nonlinear contact iteration.

## Stressing pair sequence

The geometry-derived symmetric tendon pairs remain separate from the construction stressing order. The user may reorder the verified pairs, and Project JSON persists that adopted sequence. Geometry order must not be silently treated as final stressing order.

## Safety boundary

This milestone does **not** calculate:

- Primary Prestress structural response.
- Secondary Prestress.
- Portal-Frame gravity/self-weight response.
- Temporary-support contact reactions or lift-off.
- Source-derived `f_cgp`.
- Final Elastic Shortening adoption.
- `Pe` / `Pe_eff`.

The accepted Friction/Wobble and Anchorage Set solvers are unchanged.
