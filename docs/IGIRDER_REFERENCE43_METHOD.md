# IGIRDER.REFERENCE43 — separated steel cracking parameter and strain continuation

Status: offline reference development. **Not a full composite resistance model.**
The strict published-reproduction gate is not met. Nothing from this module is
dispatched by the app or written into design result caches or Project JSON.

## Reproducible source definitions

The concrete interpretation from REFERENCE42 is retained as an explicit baseline:
Bernardo, Andrade & Nunes (2015), *Materials and Structures* 48:2169–2193,
DOI [10.1617/s11527-014-0301-z](https://doi.org/10.1617/s11527-014-0301-z),
Table 1 and Eqs.22–23, 28, 39–40, 56–63.
For the solid rectangle, K=1.45, Et=3875 K sqrt(fc), ecr=0.00008 K,
and the continuous concrete tensile peak is Et ecr. This remains a declared
interpretation; agreement with every number from the authors' program has not
been established. The Table-2 tensile strength is reported separately.

An earlier primary paper explicitly defines the cracking parameter in the
embedded-steel law: Bernardo, Andrade & Lopes (2012), *Engineering Structures*
42:278–296, Table 4, r03,
DOI [10.1016/j.engstruct.2012.04.036](https://doi.org/10.1016/j.engstruct.2012.04.036).
The DOI ending `.04.036` is printed on the primary PDF's first page.

```text
fcr_steel[psi] = 3.75 sqrt(fc[psi])
1 psi = 0.006894757293168 MPa
B = (fcr_steel/fy)^1.5 / rho
m = 1/(9B - 0.2), with the printed upper limit m <= 25
```

The psi coefficient cannot be applied directly to fc in MPa. For specimen B3,
the converted steel parameter is 1.650607899 MPa; the retained torsion-adjusted
concrete peak is 3.455022 MPa. These are separate quantities in the new audit.
Applying the 2012 definition to the 2015 dataset is an explicit candidate source
interpretation, **not proof of what the original 2015 Delphi program used**.

Three profiles are kept, using identical specimen geometry and continuation:

| Profile | Steel parameter | Nonpositive exponent denominator |
|---|---|---|
| LEGACY42 | retained concrete peak | reject |
| SOURCE2012_STRICT, the API default | converted 2012 definition | reject |
| SOURCE2012_POSITIVE_CAP | converted 2012 definition | declared extension to m=25 |

The last profile uses `m = 1/max(1/25, 9B-0.2)`. The positive-denominator cap is
the printed upper limit. Extending it through a nonpositive denominator is an
explicit interpretation requiring further evidence. It is not a fitted
beam-specific factor, the authors' verified implementation, or a production
acceptance rule. Both raw denominators, B, rho, m, and extension flags are
exported. Invalid strict cases remain in the 16-case denominator.

## Complete strain continuation

Compression magnitudes are positive; tensile steel strain is positive. Units
are N, mm, MPa, radians. The unknowns at a specified concrete surface compression
e2s are strut angle alpha and positive principal surface tension e1s. Their Mohr
relations are:

```text
el = (e1s sin(alpha)^2 - e2s cos(alpha)^2)/2
et = (e1s cos(alpha)^2 - e2s sin(alpha)^2)/2
g = e2s / [(e1s+e2s) sin(alpha)^2 cos(alpha)^2]
po t / Ao = g
Ao = (b-t)(h-t), po = 2(b+h-2t)
(4+g)t^2 - (2+g)(b+h)t + g b h = 0
```

The smaller admissible quadratic root is evaluated in a stable rational form.
The exact product for Ao is retained. The alternative expression printed after
the second equality of the 2015 Eq.40 omits t² and is not algebraically equal.
The later PC paper also states the exact product explicitly (Sect.2,
DOI [10.1186/s40069-018-0285-0](https://doi.org/10.1186/s40069-018-0285-0)).

Original force triangles supply the two residuals. A generic normal-stress
membrane equation is not substituted for the printed transverse force equation:

```text
beta_angle = atan2(st sin(alpha), sc cos(alpha))
q/t = (sc+st) sin(alpha) cos(alpha)
Al fl/(po t) = sc cos(alpha)^2 - st sin(alpha)^2
(At/s) ft/t = (q/t) tan(alpha-beta_angle)
theta = e2s/[2t sin(alpha) cos(alpha)]
```

Independent tests use the original force resultants C,T
and uncancelled compatibility equations, as well as a separate three-unknown
root, to check the condensed formulation.

Near zero load, small compressive steel strains can occur. They use elastic
compression without zero clipping; compression yielding is outside scope.
Residuals are scaled by `fc*min(e2s/eps0,1)` so a tiny absolute force does not
hide a large loading-stage-relative equilibrium error.

Continuation starts at e2s=1e-8, not a manufactured origin. It stops at the
located first sampled/bracketed steel tensile-strain boundary or the declared
concrete surface-strain limit. A boundary maximum is a valid endpoint. An
unconverged point aborts that case; no gap is filled or branch sorted into order.
Peak refinement is confined to its strain window and the located material
boundary. Grid refinement checks the peak and boundary behavior.

Two distinct maxima are retained: the maximum of the full computed interval,
and the maximum in e2s>=0.0005 for direct comparison with REFERENCE42. The latter
window is a diagnostic convention, **not an equation defining cracking**.
If a material limit occurs earlier, its curve is complete and the comparison
peak is absent. `state_at_tensile_strain` locates an explicitly named strain
event without claiming it reproduces the published cracking torque Tcr.

## Evidence and acceptance

The fixture `qa/benchmarks/igird_reference42_2015.json` is unchanged. All three
profiles use the same first 16 consecutive Table-2 specimens selected before
the new comparison. The existing 1% torque **and** twist reproduction gate is
unchanged. Per-case mismatch, strict scope rejection, and domain extension are
separate output fields. Experimental torque ratios are descriptive statistics,
with no invented acceptance band or strength factor.

The following are different checks:

| Check | Evidence in this milestone | Current conclusion |
|---|---|---|
| Software/mechanics implementation | independent root, forces, compatibility, scaling, rotation, endpoints, API and regression tests | selected tests pass |
| Reproduce selected published theoretical points | fixed 16 cases, three explicit material profiles, unchanged tolerance | not reproduced |
| Rectangular RC physical prediction | measured torque ratios reported | no new structural acceptance claimed |
| Flanged-section redistribution | 2019 two closed-cage subdivisions are a possible reference | not implemented/validated here |
| PSC I-girder + later-cast slab | requires staged initial strain/stress and actual section topology | not established |
| U-dowel + slab mesh joint | requires coupled slip/opening, anchorage and concrete failure | not established |
| Concurrent six-force resistance | requires one equilibrium solution with shared material resources | not established |
| Code nominal/design full composite Vn,Tn,V–T | depends on the preceding system checks and applicable code route | not accepted |

The flanged reference is Bernardo (2019), DOI
[10.3390/app9132730](https://doi.org/10.3390/app9132730). Its independent closed
cages must not be silently replaced by an open U and slab mesh. The PC reference
above assumes uniform longitudinal prestress under pure torsion; it is not
validation of eccentric girder prestress plus construction-stage slab action.

Before a full-composite design result can be enabled, a solver must represent
the actual loading boundary and force path, conserve each concrete/steel
inventory, and satisfy both section equilibrium and interface compatibility.
Verification must then cover suitable flanged and prestressed references, joint
slip/anchorage and failure, concurrent six-force loading, and mesh/length
sensitivity. Removing dowels need not make total resistance zero when slab
ends are loaded directly; the boundary and component force transfers must be
examined. Neither common twist alone nor a scalar addition of separate
girder/slab/dowel strengths meets these requirements.

## Reproduce the audit

From the repository root, with the existing requirements installed:

```bash
python tools/run_igird_reference43.py --output qa/evidence/igird_reference43
python -m pytest tests/test_igird_reference43.py -q
```

The audit exits 2 while acceptance remains unmet. Evidence files are audit JSON,
full state curves JSON, comparison CSV, and separate steel material trace CSV.
The selected regression module list and JUnit XML are stored beside them. No
research results are persisted in the user's Project JSON, no new inputs are
requested, and no main-app capacities are changed by this offline milestone.
