### CROSSBEAM.PTA1A - Jacking Force Trace Wording Hotfix

PTA1A tightens the Crossbeam prestress force-source audit wording after visual
QA of the Tendon System and Tendon Profile pages.  The hotfix keeps PTA1 force
source arithmetic unchanged and reduces the risk that repeated station rows are
mistakenly summed as independent tendon forces.

#### What changed

- Renames the Tendon System force table heading to `Jacking Force Source Audit (Pj)`.
- Renames the Tendon Profile trace heading to
  `Jacking force station trace (do not sum station rows)`.
- Removes `Active Pj credit (kN)` from the station trace table.
- Renames the station trace force column to `Pj source per tendon (kN)`.
- Adds a visible note that station trace rows repeat the same per-tendon force
  source and must not be summed for total active `Pj`.
- Keeps the by-tendon summary as the only visible place to review total active
  `Pj` credit.

#### Scope guard

- No `Pj` formula changed.
- No Tendon System schema or Project JSON shape changed.
- No prestress-loss, SLS, ULS, anchorage-zone, deviator-force, D-region, report,
  rebar workflow, Segment Layout, Section Builder, or solver behavior changed.

#### Repo summary

Polish Crossbeam PTA1 jacking-force source wording and remove repeated active-Pj credit from station trace rows so users do not sum per-station force values as independent tendon forces.
