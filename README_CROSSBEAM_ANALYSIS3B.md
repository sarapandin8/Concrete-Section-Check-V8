# CROSSBEAM.ANALYSIS3B — Segment-Owned Shear/Torsion Capacity and One-Sided Physical-Joint Plot Closeout

## Baseline

Started only from:

```text
concrete-section-pro_CROSSBEAM-ANALYSIS3A-torsion-chart-completeness-scale-semantics.zip
SHA-256: 3deccbab9b1ad3777920e63636f6726ec21cd0cf9692a4a226bdc3ac39308a22
```

## Scope

This milestone corrects the Crossbeam ULS Shear and standalone ULS Torsion diagrams so Segment-owned capacity is never interpolated through a Precast physical joint or through a Solid/Hollow Section-ID change.

The numerical ACI 318-19 resistance equations are unchanged.

## Engineering behavior

### Physical joints

Every internal Segment boundary is obtained directly from the active Segment Layout. For each physical joint and each Load Case, the adapter now creates two independent rows:

```text
J#-L = left Segment one-sided value (s−)
J#-R = right Segment one-sided value (s+)
```

The two sides preserve their own:

- Segment and Section ID;
- row-coupled P, V2, T, and M3 source;
- reinforcement and tendon source;
- shear φVc / φVn;
- torsion φTth / φTn;
- utilization and source-recovery audit.

No averaging is permitted and no interpolation crosses a physical joint. Source recovery is exact-first, then one-sided from station-force rows located inside the adjacent Segment. A one-sided extrapolation used solely to reach the Segment boundary is limited to one source-row spacing and is reported explicitly in the audit table; unavailable sides remain visible as source notes rather than silently borrowing the opposite Segment.

Physical-joint shear/torsion transfer remains `REVIEW REQUIRED`; plotting the one-sided section capacities does not certify transfer across the joint.

### ULS Shear chart

- Vu remains a station-dependent response diagram.
- φVc and φVn may vary inside a Segment under the accepted ACI prestressed shear route.
- Capacity traces are constructed separately for each Segment.
- Traces are broken at every physical joint and across every support footprint.
- Solid/Hollow or Rebar-source changes are never connected by a diagonal line.
- Actual left/right joint-side Vu, φVc, and φVn values are plotted with small station offsets for legibility while hover/audit retain the exact joint station.

### ULS Torsion chart

- φTth and φTn are plotted as horizontal Segment-owned capacities.
- A Solid/Hollow change is shown as a step/discontinuity, never a linear slope.
- Traces are broken at every physical joint and across support footprints.
- Actual left/right joint-side Tu, φTth, and φTn values are plotted independently.
- The governing black marker remains `Tu/φTn`; longitudinal-Al and section-limit utilization are not misrepresented on the force/capacity graph.

## UI and audit

The accepted Bridge/Beam and Crossbeam visual language is retained. Both workspaces include a compact `Physical joint one-sided capacities` table containing the exact joint station, side, Segment, Section ID, demand source, capacity, utilization, source stations, and extrapolation ratio.

## Files changed

```text
concrete_pmm_pro/analysis/crossbeam_uls_shear.py
concrete_pmm_pro/analysis/crossbeam_uls_torsion.py
concrete_pmm_pro/ui/analysis_page.py
tests/test_crossbeam_analysis2_uls_shear.py
tests/test_crossbeam_analysis3_uls_torsion.py
tests/test_crossbeam_analysis3b_joint_capacity_plot.py
README_CROSSBEAM_ANALYSIS3B.md
```

## QA completed

```text
python -m compileall -q app.py concrete_pmm_pro tests
PASS

Focused ANALYSIS2 / ANALYSIS3 / ANALYSIS3B:
37 passed

Crossbeam-selected suite:
567 passed
5 baseline-existing failures

Shared Analysis + Bridge/Beam ULS chart/navigation regression:
124 passed
```

The five Crossbeam-selected failures are unchanged legacy source-string assertions in old Prestress-Loss / external-FEA handoff milestones and are unrelated to this change.

A full repository suite was not run for this milestone. Live deployed Streamlit visual QA remains required after uploading the release ZIP.

## Repo summary

```text
Plot Segment-owned Crossbeam shear and torsion capacities without Solid/Hollow interpolation and add independently recovered left/right demand and capacity values at every Precast physical joint.
```
