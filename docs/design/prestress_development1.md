# PRESTRESS.DEVELOPMENT1 — Railway U-Girder Transfer / Development Length Evidence

## Status

`PRESTRESS.DEVELOPMENT1` adds guarded transfer-length and development-length evidence for Railway U-Girder strand rows.

This milestone is **engineering-review evidence only**. It is **not final code-certified design** and is not Engineer-of-Record certification.

## Scope

The milestone reads the active Railway U-Girder strand/debonding table and reports, by strand row:

- strand diameter and area,
- final effective prestress stress estimate,
- review `fps` basis,
- transfer length `lt`,
- development length `ld`,
- left/right sleeve termination and full-development stations,
- bonded length to midspan,
- development D/C screen,
- guarded status and blocked-final-claim notes.

## Guardrails

The evidence table uses a visible AASHTO/ACI-compatible screening basis:

```text
lt = max(60db, fpe·db/3)
ld = max(lt, (fps - 2/3 fpe)db)
```

Stress units are internally converted from MPa to ksi for the common strand-development equation form.

This milestone does **not**:

- apply a transfer-length force ramp to SLS or ULS solvers,
- certify debonded strand anchorage,
- perform end-zone bursting/spalling design,
- design anchorage-zone reinforcement,
- change station-based debond participation logic,
- change SLS stress equations. No SLS solver equations are modified,
- change ULS flexure/shear/torsion equations,
- change geometry, section properties, load combinations, or project schema.

## Certification boundary

Allowed wording is limited to:

```text
Engineering Review PASS
Engineering Review FAIL
REVIEW
```

Do not use:

```text
Code-Certified PASS
Final Design PASS
Engineer-Certified PASS
```

Final certification still requires development-length benchmark validation, debonded strand anchorage detailing, end-zone bursting/spalling checks, and Engineer-of-Record review.
