# Concrete Section Pro — IGIRDER.ULS7

Continuation of the supplied IGIRDER.ULS6F baseline, dated 2026-10-03.

## Run the production app

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Use **Bridge Beam / Girder → Precast I-Girder → AASHTO LRFD 9th Edition**.
The app preserves the accepted Construction Flexure, positive Final Composite
Flexure, Interface Shear, standalone Shear and standalone Torsion routes.

## New concurrent gate

**Analysis → ULS Strength → Shear + Torsion** checks concurrent Mu, Nu, Vu and
Tu from one physical row/case, including physical support faces. It implements
AASHTO 5.7.3.6.1 transverse allocation and 5.7.3.6.3-1 longitudinal force.

- One physical hoop is counted once. Av/s is the effective shear-leg area per
  spacing; At/s is one closed-loop leg area per spacing.
- Required transverse area is max(shear Av/s, minimum Av/s) + 2At/s.
- Vs relief uses the hoop area remaining after torsion allocation and is capped
  at |Vu|/phi. General Procedure beta/theta uses torsion-modified Veff.
- Longitudinal resistance uses developed Aps times nominal fps, plus developed
  ordinary As times its actual material fy. Ordinary bars retain the same
  identity/source as Flexure. No separate torsion-only table is introduced.
- Nominal fps reuses AASHTO section equilibrium and the accepted bonded-strand
  model with the verified positive composite section. Minimum tension-side fps
  is a conservative group-sum bound. fpu is a development-length screen, never
  an assumed nominal resistance. Optional deck bars are excluded from this new
  fps source; accepted Flexure remains unchanged.
- App Nu is compression-positive; AASHTO Nu is tension-positive. The stored
  trace displays both signs and every longitudinal force term.
- Veff/compression-limit D/C is an **additional conservative guard**, explicitly
  labeled as such. It is not an ACI Aoh/ph stress shortcut.

Before final PASS, open **Sections → Rebar → Longitudinal Rebar →
Longitudinal development — Shear + Torsion**. Confirm that every active ordinary
bar is continuous over the full physical span and provide the governing verified
straight-bar development length, or explicitly confirm full strength anchorage
at each end. Enter a drawing/calculation reference. Unconfirmed development
receives zero ordinary strength/stiffness credit and withholds PASS. This common
full-span assumption is unsuitable for cut-off bars or mixed anchorage details.

Confirm torsion-qualified closed hoops, hooks and corner bars/tendons in the
existing Transverse Rebar inputs. Use the new checkbox “Existing longitudinal
bars/tendons are distributed around the selected hoop perimeter” to confirm
perimeter distribution from the same longitudinal steel and cage drawing. Missing
coverage or confirmation remains DATA REQUIRED/REVIEW. Pretensioned Aps*fps must
exceed As*fy on the checked tension side independently of the numerical F/R gate.

## Result ownership

New combined version: `IGIRDER.ULS7.concurrent-vt-longitudinal`.
Existing Shear/Torsion/Flexure/Interface versions remain unchanged.
Development inputs affect only the combined engineering signature. Old combined
pending packages are invalidated. Current-hash checks prevent stale combined
PASS in Summary/Report when sources or development inputs change.

Analysis remains check-specific. Result Summary performs cross-check aggregation
from stored packages. Report / QA displays stored equations/variables and all
station gates without rerunning the solver. Summary may show **PASS — COMPONENT**
for accepted standalone transverse Torsion only when its full coverage/detailing
and the current concurrent longitudinal gate pass; the standalone stored result
is not rewritten. Missing other stage checks keep Overall ULS INCOMPLETE.

## QA and scope

ULS6F running-app visual closeout is complete: 21 finite physical stations over
0–20 m, including x=3,6,14,17 and both ends; plotted phiTn values match stored
Torsion audit values. Deliberately unqualified Z3 retains real gaps. This closes
the standalone transverse component implementation, not the strength acceptance
of the high-Tu QA section, which correctly fails.

The QA fixture is reconstructed from the supplied minimum five-zone configuration
and baseline parametric I-geometry. No original I-Girder project JSON was supplied;
its numeric capacities are not claimed to reproduce an undocumented original
model. See `qa/uls6f_runtime_audit.json` and `qa/evidence/`.

Reproduce the real renderer fixtures:

```bash
streamlit run qa/igird_uls6f_runtime.py
streamlit run qa/igird_uls7_runtime.py
python qa/check_uls6f_runtime_audit.py
```

Engineering benchmarks and gates are in `tests/test_igird_uls7_concurrent_vt.py`.
The prepackage 35-module related regression passed **248 tests**; the last
Summary/legend-focused batch passed **51 tests** and the subsequent perimeter
UI/source/cache-focused closeout passed **83 tests**. A final fresh-extract result,
archive hash, byte size and entry count are supplied in the companion release
manifest. The full repository suite was not run; no full-suite PASS is claimed.
Seventy accepted solver/source helper bodies are identical to the supplied
baseline (`qa/protected_solver_comparison.json`).

Scope is normal-weight, uniaxial solid pretensioned I-Girder sectional V+T with
straight strands (Vp=0, lambda_duct=1). At zero Mu above the torsion threshold,
both tension halves are checked conservatively. Below threshold the default
bottom chord owns the zero-Mu shear-only check. Negative composite flexure,
biaxial actions, lightweight concrete, fatigue, bearing/D-regions, actual hooks,
laps, strand overhangs and shop-drawing verification remain separate review
items. Passing this gate alone does not certify the entire member or bridge.
