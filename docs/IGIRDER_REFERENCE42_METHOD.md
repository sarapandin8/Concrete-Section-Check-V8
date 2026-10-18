# IGIRDER.REFERENCE42 — published-equation torsion reference

This development milestone adds an offline nonlinear reference kernel and a
reproducible comparison audit. It does **not** deliver the project's full
composite nominal or design Vn, Tn or V–T resistance. The published reproduction
gate currently fails. Streamlit does not call this module.

## Source and model identity

- Bernardo, L.F.A.; Andrade, J.M.A.; Nunes, N.C.G. (2015). Generalized softened
  variable angle truss-model for reinforced concrete beams under torsion.
  Materials and Structures 48:2169–2193.
  DOI: https://doi.org/10.1617/s11527-014-0301-z
- Author/university-hosted full text:
  https://cmadeubi.wordpress.com/wp-content/uploads/2015/10/materials-and-structures-published-online-15-may-2014-on-paper-2015.pdf
- Common-twist assembly principle: Bernardo (2019), Modeling the Full Behavior
  of Reinforced Concrete Flanged Beams under Torsion, Applied Sciences 9:2730.
  https://doi.org/10.3390/app9132730
- Constitutive-law context: Teixeira and Bernardo (2021), Materials 14:1260.
  https://doi.org/10.3390/ma14051260

The pinned implementation profile is
`2015_table1_continuous_solid_K1.45`. Its interpretation must remain explicit;
it is not asserted to reproduce the authors' original Delphi implementation.
The source PDF is linked, not redistributed in the repository.

## Coordinates, signs and units

The reference is a solid rectangular, nonprestressed RC cross-section with
one closed transverse cage, under positive pure torque. Longitudinal and
transverse steel strains are positive tensile strains. Concrete compressive
stress and strain are positive magnitudes. All calculations use N, mm, MPa,
radians; twist is radians/mm. For display, torque/1e6 is kNm and
twist*1000*180/pi is degrees/m.

`At/s` is the area of **one** transverse branch per spacing. Do not insert both
legs again. Published cm2/m values are multiplied by 0.1 to obtain mm2/mm.
Longitudinal cm2 values are multiplied by 100 to obtain mm2.

For b, h and hoop centreline dimensions b1, h1:

```
Ac = b*h
u  = 2*(b1+h1)
rho_l = Al/Ac
rho_t = (At/s)*u/Ac
Ao = (b-t)*(h-t)
po = 2*(b+h-2*t)
```

The **hoop** perimeter u follows the original 2015 section 6 and Table 2.
It is distinct from both the outer perimeter and evolving po. Later
restatements use an outer-perimeter definition; those profiles are not mixed
into this implementation. The exact product for Ao retains t2. The linear
expression printed after that product in original Eq.40 is an approximation,
not an additional exact identity.

## Material interpretation

Original Table 1 gives K=1.45 for solid sections:

```
Ec_tension = 3875*K*sqrt(fc)
eps_cr = 0.00008*K
fcr = Ec_tension*eps_cr
eta = rho_l*fly/(rho_t*fty)
eta_prime = min(eta,1/eta)
beta = min(0.9,5.8/sqrt(fc))/sqrt(1+400*eps_1/eta_prime)
```

Continuity between the specified ascending and descending tensile laws is
the stated reason for deriving fcr as Ec*eps_cr. That value is generally
different from fctm in Table 2. Both values are shown in the audit. No
beam-specific tensile multiplier or separately tuned steel cracking stress
has been fitted to the targets. Whether the original calculation used this
same interpretation for the embedded-steel B parameter remains unresolved.

The compression and tension block stresses are exact thickness averages
of Table-1 point laws, using linear strain gradients, original Eqs.60–63.
Their implementations are verified against independent numerical quadrature
on both sides of the transition, rather than testing a duplicated formula.

The embedded steel law follows Table 1. If 9B-0.2 <= 0, the printed law does
not define a physically usable positive exponent. This implementation raises
a scope error; it does not invent a limiting m=25 branch. Compression of steel
before cracking is also outside this reference implementation.

## Compatibility and nonlinear equilibrium

For specified surface compressive strain e2 and unknown tensile steel
strains el, et, original Eqs.56–59 can be condensed:

```
kl = el/e2 + 1/2
kt = et/e2 + 1/2
alpha = atan(sqrt(kl/kt))
g = 1/(2*kl)+1/(2*kt) = po*t/Ao
(4+g)*t2 - (2+g)*(b+h)*t + g*b*h = 0
eps_1s = 2*el+2*et+e2
eps_1 = eps_1s/2
theta = e2/(2*t*sin(alpha)*cos(alpha))
```

The smaller positive thickness root is evaluated without subtractive
cancellation. The independent tests recover the original uncancelled
compatibility equations and Mohr/Bredt relations.

With sc and st the average concrete compression and tension, take dv=1 mm:

```
C = sc*t*cos(alpha)
T = st*t*sin(alpha)
beta_angle = atan2(T,C)
gamma = alpha+beta_angle
gamma_prime = alpha-beta_angle
MT = 2*Ao*hypot(C,T)*sin(gamma)
Al*fl = MT*po/(2*Ao)*cot(gamma)
(At/s)*ft = MT/(2*Ao)*tan(gamma_prime)
```

These are the literal published force triangles and Eqs.22–23. In particular,
the transverse relation is **not** replaced with the ordinary membrane
normal-stress expression `sc*sin(alpha)^2-st*cos(alpha)^2`: they do not agree
in general when concrete tension remains. Tests check both the force
triangles and the original Eq.49 angle expression independently.

The solver uses bounded nonlinear least squares in the logarithms of
positive steel strain/e2 ratios. The acceptance residual is scaled by fc
and must not exceed 1e-9. An unconverged point raises an error and is never
connected across a missing interval or zero-filled in a chart.

## Continuation, peaks and branch limits

The default reference continuation runs e2=0.0005 through the declared
surface-concrete strain limit 0.0035. Steel strain is bounded by 0.010.
The starting strain is a declared numerical interval, **not a computed
cracking strain or cracking torque**. No elastic origin is manufactured.

The largest interior sampled torque is refined by bounded minimization;
every objective evaluation solves the full simultaneous equilibrium again.
Step refinement verifies the peak stability. A boundary maximum or an
unresolved steel-limit bracket yields an incomplete branch. Only a completed
declared interval with an interior peak is marked NUMERICALLY_COMPLETE.
This status is unrelated to structural validation or design acceptance.

Published Tu and theta_u are compared with the computed post-cracking peak
and its twist. The endpoint convention remains explicitly under audit;
the comparison is not silently equated with a full-curve reproduction.

## Common-twist assembly and inventory conservation

`combine_at_common_twist` implements the mathematical reference rule
`MT_total(theta)=sum(MT_i(theta))`. It interpolates only inside the common
available twist interval and stops at the first component's end. The
piecewise-linear sampled maximum does not add independently occurring
component peak torques. A synthetic independent example verifies a total
peak of 7 when individual peaks of 5 and 4 occur at different twists.

Each cell must refer to explicit concrete, longitudinal-steel and
transverse-steel inventory IDs. Allocated quantities come from its actual
input rectangle and steel areas. Shared allocations cannot exceed the
available supply. The caller must use the actual union area for overlapping
concrete and the actual bar supply; arbitrary new IDs do not establish
physical independence. This bookkeeping is necessary but is not itself a
proof of a local load path or bond/development.

This assembly assumes ideal common twist. It contains **no** joint slip,
opening, dowel bending, anchorage, common-node warping solution or interaction
law. It therefore must not be mapped automatically to the project's open
U-dowels and slab mesh, nor presented as full composite compatibility.

## Benchmark audit and explicit failed gate

Fixture: `qa/benchmarks/igird_reference42_2015.json`.
Selection: the first 16 consecutive Table-2 specimens, B3–B10, C4–C6,
G3–G5 and G7–G8, with no selection by agreement. Areas, strengths and
strain inputs are literal published values. The anomalous C5 printed
percentage is not copied over its actual reinforcement area.

The 1% comparison tolerance is a strict **code reproduction gate**, not
a newly asserted statistical structural acceptance band. It applies to both
published torque and twist. Agreement with measured torques is reported as
ratios without an invented structural PASS threshold. All mismatches remain
in the report. The command exits 2 when the reproduction gate fails.

Current result: 16 numerical curves, 3 matched published points, 13
mismatches; overall NOT_REPRODUCED. This result prevents promoting the
kernel to the project's resistance calculation. Production acceptance stays
false even for an individually matched published point.

Run from a normal app environment with requirements installed:

```bash
python tools/run_igird_reference42.py --output qa/evidence/igird_reference42
python -m pytest tests/test_igird_reference42.py -q
```

Reference curve JSON is offline QA evidence. It is not project JSON,
production result-cache persistence, or a stored design result.

## Actual project and next technical work

Project31/COVER38 has a prestressed I-girder and a slab cast at a different
stage, with 90-degree U hooks and top/bottom mesh. This reference does not
resolve those physical conditions. The existing confirmed bar/strand
coordinates and linked dowel zoning do not need to be changed or re-entered
to run the reference audit.

Next, resolve the concrete/embedded-steel material interpretation against
the published response, keeping source variants explicit and testing the
same predetermined specimens. Then establish the appropriate flanged/PC
references, interface opening/slip and anchorage response, and coupled
simultaneous N–M2–M3–V2–V3–T validation. Pure-torsion rectangle agreement alone
cannot establish the project's full composite Vn/Tn/V–T resistance.

No phi factor, design-code compliance claim, beneficial default interface
stiffness, full-cage substitution or automatic U-dowel strength increment
is supplied in this milestone.
