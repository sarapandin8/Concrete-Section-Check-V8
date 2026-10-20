"""Coupled N-M sandwich stress-field review with actual four-mat positions.

This is a statically admissible, finite-field section check, not an optimizer
of the complete shell resistance domain. Concrete is compression-only; steel
is tension-only. Conservative AASHTO 2020 STM component limits are adopted for
the field. That adoption does not certify an entire STM or bridge deck design.

Units: membrane/shear kN/m = N/mm, moments kN-m/m * 1000 = N-mm/mm.
CSI positive bending gives compression at +local 3: K = integral(z*sigma)=-M.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import time

import numpy as np
import pandas as pd

from concrete_pmm_pro.analysis.igird_slab_layers import detail_from_state, resolve, RULE, ORDER_KEY
from concrete_pmm_pro.analysis.igird_dowel_detail35 import mesh_inventory
from concrete_pmm_pro.analysis.slab_shell56_geometry import recover, steel_axis_forces
from concrete_pmm_pro.core.design_code import workflow_project_code_label_from_session
from concrete_pmm_pro.io.slab_shell_import import current_package
from concrete_pmm_pro.analysis.slab_connections59 import layout as connection_layout, annotate as annotate_connections, INCLUDED, REASON
from concrete_pmm_pro.analysis.igird_shear_support import support_settings

VERSION = "SLAB.ENDZONE60"
RESULT_KEY = "slab_shell55_strength56_result"  # cleared by the existing Project JSON input transaction
GROUPS = ("Top longitudinal", "Bottom longitudinal", "Top transverse", "Bottom transverse")
PHI_TIE, PHI_CONCRETE, NU_CONCRETE, PHI_SHEAR = .9, .7, .45, .9
ES = 200000.
SCOPE = ("N-M sandwich field review using AASHTO component limits; not a complete code acceptance. "
    "One-way shear is a separate conservative section screen. No transverse-shear tie force is added to the N-M steel areas. "
    "Nonzero V keeps combined N-M-V resistance at REVIEW; passing separate components does not establish their interaction. "
    "An independent N=0 RC strip reference and sufficient 1.33Mu minimum screen do not replace the coupled field. "
    "Anchorage, cover/exposure, the Mcr minimum branch and combined-NM minimum qualification, fatigue, punching/local wheel effects and SLS remain separate.")


def _positive(value, name):
    if isinstance(value, bool):
        raise ValueError(name + " must be a positive finite number")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(name + " is missing") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(name + " must be a positive finite number")
    return value


@dataclass(frozen=True)
class SlabSteel:
    area: np.ndarray       # mm²/m: top L, bottom L, top T, bottom T
    fy: np.ndarray         # MPa
    centre: np.ndarray     # distance from corresponding exposed surface, mm
    diameter: np.ndarray
    spacing: np.ndarray
    fc: float

    def __post_init__(self):
        for name in ("area", "fy", "centre", "diameter", "spacing"):
            value = np.asarray(getattr(self, name), dtype=float)
            if value.shape != (4,) or not np.isfinite(value).all() or np.min(value) <= 0:
                raise ValueError("Four positive finite slab steel values are required: " + name)
            object.__setattr__(self, name, value)
        _positive(self.fc, "Deck f′c")

    def z(self, h):
        h = np.asarray(h)
        return np.column_stack((h/2-self.centre[0], -h/2+self.centre[1],
            h/2-self.centre[2], -h/2+self.centre[3]))


def steel_from_state(state):
    code = workflow_project_code_label_from_session(state)
    if code != "AASHTO LRFD 9th Edition":
        raise ValueError("SLAB.CHECK56 supports the documented AASHTO LRFD 9th Edition only")
    params = dict(state.get("section_parameters") or {})
    cfg = detail_from_state(state)
    cfg[ORDER_KEY] = RULE
    # Force the requested physical layer rule in this pure reader, without
    # altering another workflow's inputs or derived covers.
    effective = resolve(params, cfg)["parameters"]
    rows = mesh_inventory(cfg, effective)
    values = {"area": [], "fy": [], "centre": [], "diameter": [], "spacing": []}
    for label, row in zip(GROUPS, rows):
        db = _positive(row["Diameter_mm"], label+" diameter")
        cover = _positive(row["Clear_cover_mm"], label+" clear cover")
        values["area"].append(_positive(row["As_mm2_per_m"], label+" area"))
        values["fy"].append(_positive(row["fy_MPa"], label+" fy"))
        values["centre"].append(cover+db/2)
        values["diameter"].append(db)
        values["spacing"].append(_positive(row["Spacing_mm"], label+" spacing"))
    fc=_positive(params.get("deck_fc_MPa"), "Deck f′c")
    if fc>15*6.894757293:
        raise ValueError("Deck f′c exceeds the documented 15 ksi range of the adopted concrete component limit")
    assigned=params.get('deck_topping_material_name') or state.get('deck_topping_material_name')
    for material in state.get('concrete_materials') or []:
        raw=material if isinstance(material,dict) else material.model_dump()
        if raw.get('name')==assigned and float(raw.get('density_kg_m3',2400))<2160:
            raise ValueError("This slab preview assumes normal-weight concrete; the assigned deck material is outside that scope")
    return SlabSteel(**{k: np.array(v) for k, v in values.items()}, fc=fc)


def fingerprint(state):
    package = current_package(state)
    if package is None:
        return None
    params = state.get("section_parameters") or {}
    detail = detail_from_state(state)
    assigned=params.get('deck_topping_material_name') or state.get('deck_topping_material_name')
    inputs = {"version": VERSION, "source": package.signature,
        "code": workflow_project_code_label_from_session(state),
        "params": {k:v for k,v in params.items() if k.startswith("deck_long_rebar_") or k in ("deck_fc_MPa", "B1_mm", "D1_mm")},
        "preset": (state.get("section_preset_key"), state.get("section_preset_name")),
        "bearing_end_exclusion": {k:v for k,v in support_settings(state).items() if k != 'note'},
        "mesh": detail.get("slab_transverse_mesh"), "order": RULE,
        "deck_name": assigned,
        "density_sources": [{"name": (m if isinstance(m,dict) else m.model_dump()).get('name'),
            "density": (m if isinstance(m,dict) else m.model_dump()).get('density_kg_m3')}
            for m in state.get('concrete_materials') or [] if (m if isinstance(m,dict) else m.model_dump()).get('name')==assigned]}
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, default=str).encode()).hexdigest()


def current(state):
    result = state.get(RESULT_KEY)
    if not isinstance(result, dict) or result.get("fingerprint") != fingerprint(state):
        return None
    return result


def wood_armer(moment):
    """Conservative (not optimized) orthogonal bending-only reference, CSI signs."""
    moment = np.asarray(moment, dtype=float)
    m1, m2, twist = moment.T
    return np.maximum(0., np.column_stack((-m1+abs(twist), m1+abs(twist),
                                          -m2+abs(twist), m2+abs(twist))))


def temperature_minimum(h, fy):
    """AASHTO 5.10.6: b→∞ is a conservative bound for every finite slab width.

    Per face/direction, 0.11..0.60 in²/ft; fy credit capped at 75 ksi.
    This is shrinkage/temperature reinforcement, not the flexural-minimum gate.
    """
    h, fy = np.asarray(h), np.asarray(fy)
    area_in2_ft = np.clip(1.30*(h[:, None]/25.4)/(2*np.minimum(fy/6.894757293, 75)), .11, .60)
    return area_in2_ft*645.16/304.8*1000


def _uniaxial_fields(n, k, diag_t, diag_b, zt, zb, zs_t, zs_b, cap_t, cap_b):
    """Candidate exact axial/moment equilibria in one steel direction.

    Free tensile resultants plus nonnegative axial concrete compression at
    each face. Direct compression and parallel steel tension at that same
    face are mutually exclusive. Diagonal compression may coexist with both
    steel directions, as in the standard cracked-membrane idealization.
    """
    dz = zs_t-zs_b
    total = n+diag_t+diag_b
    first = k+zt*diag_t+zb*diag_b
    free_t = (first-zs_b*total)/dz
    free_b = total-free_t
    at, ab = (zt-zs_b)/dz, (zb-zs_b)/dz
    bt, bb = 1-at, 1-ab
    zero = np.zeros_like(n)
    def divide(a, b):
        return np.divide(a, b, out=np.full_like(a, np.nan), where=abs(b)>1e-12)
    ct = np.stack((zero, divide(-free_t, at), zero, divide(-bb*free_t+ab*free_b, at*bb-ab*bt)))
    cb = np.stack((zero, zero, divide(-free_b, bb), divide(bt*free_t-at*free_b, at*bb-ab*bt)))
    st, sb = free_t+at*ct+ab*cb, free_b+bt*ct+bb*cb
    valid = np.isfinite(ct+cb+st+sb) & (ct>=-1e-8) & (cb>=-1e-8) & (st>=-1e-8) & (sb>=-1e-8)
    valid &= ~((ct>1e-7) & (st>1e-7)) & ~((cb>1e-7) & (sb>1e-7))
    return np.maximum(ct, 0), np.maximum(cb, 0), np.maximum(st, 0), np.maximum(sb, 0), valid


def principal_max(xx, yy, xy):
    return .5*(xx+yy)+np.hypot(.5*(xx-yy), xy)


def _shear(h, demand, steel, max_m, max_n):
    """Conservative one-way screen; no unreported shear reinforcement credit.

    A geometric lower bound for section dv is used, independently of the N-M
    face search. It is not a claim of available core reserve in that field.
    Shallow sections without principal axial tension use 5.7.3.4.1. Otherwise .006 strain is used
    only when an intentionally conservative strain bound does not exceed it.
    No guessed aggregate size: dg=0 gives a conservative crack-spacing bound.
    """
    dv = np.maximum(.9*(h-steel.centre.max()), .72*h)
    shallow = (h < 16*25.4) & (max_n <= 1e-9)
    # 1/2 min mat area bounds projected orthogonal steel stiffness. The factor
    # two also covers the fully tensile-face strain rule in 5.7.3.4.2.
    eps_bound = 2*(np.maximum(max_m*1000/dv, demand)+.5*np.maximum(max_n, 0)+demand)/(ES*.5*steel.area.min()/1000)
    qualified = (demand <= 1e-12) | shallow | (eps_bound <= .006)
    sxe = np.clip(h*1.38/.63,12*25.4,80*25.4)  # dg=0, conservative sx=h, code bounds
    beta_general = 4.8/(1+750*.006)*51/(39+sxe/25.4)
    beta = np.where(shallow, 2., beta_general)
    shear_stress = .0316*np.sqrt(steel.fc/6.894757293)*6.894757293*beta
    vn = np.minimum(shear_stress, .25*steel.fc)*dv
    capacity = PHI_SHEAR*vn
    dc = demand/capacity
    # If strain applicability is unresolved, retain the NM review but never
    # call this screening number a qualified code resistance.
    return np.where(qualified, dc, np.nan), qualified, dv, beta, eps_bound, capacity


def section_check(h, membrane, moment, transverse, steel):
    """Vectorized finite-field search, retaining a single coherent field per row."""
    h = np.asarray(h, dtype=float)
    membrane, moment, transverse = map(lambda v: np.asarray(v, dtype=float), (membrane, moment, transverse))
    count = len(h)
    if membrane.shape != (count, 3) or moment.shape != (count, 3) or transverse.shape != (count, 2):
        raise ValueError("Each source row requires three membrane, three moment and two shear components")
    if not np.isfinite(np.column_stack((h, membrane, moment, transverse))).all():
        raise ValueError("Missing / non-finite shell actions or thickness")
    zs = steel.z(h)
    if np.any(h<=0) or np.any(zs[:, [0, 2]]<=zs[:, [1, 3]]):
        raise ValueError("Opposite reinforcement layers overlap in the local slab thickness")
    # Include bar radius in the physical fit check.
    if np.any((steel.centre+steel.diameter/2)[None, :] >= h[:, None]):
        raise ValueError("Slab reinforcement does not fit the local thickness")
    if np.any((steel.centre[[0,2]]+steel.diameter[[0,2]]/2+
               steel.centre[[1,3]]+steel.diameter[[1,3]]/2)[None, :] > h[:, None]):
        raise ValueError("Top and bottom reinforcement mats physically overlap")
    capacities = PHI_TIE*steel.area*steel.fy/1000
    shrinkage = temperature_minimum(h, steel.fy)
    min_dc = np.max(shrinkage/steel.area, axis=1)
    spacing_dc = np.max(steel.spacing[None, :]/np.minimum(1.5*h[:, None], 18*25.4), axis=1)
    n1, n2, n12 = membrane.T
    k1, k2, k12 = (-moment*1000).T
    max_m = np.maximum(abs(principal_max(*moment.T)), abs(-principal_max(*(-moment).T)))
    max_n = principal_max(n1, n2, n12)
    v = np.linalg.norm(transverse, axis=1)
    # This search equilibrates only N and M. The previous release appended an
    # unconditional full shear-chord force to BOTH faces. That is neither the
    # shell sandwich allocation nor a qualified application of 5.7.3.5. Do not
    # silently replace it with a half-force: cracked-core resistance, the signed
    # xy increment and core/cover compatibility would still be unverified.
    best = np.full(count, np.inf)
    fields = np.full((count, 12), np.nan)
    # Fixed fractions plus demand-based exact roots for the uniaxial benchmarks.
    candidate_depths = [h*f for f in np.linspace(.025, .45, 13)]
    wa = wood_armer(moment)
    fd = PHI_CONCRETE*NU_CONCRETE*steel.fc
    candidate_depths += [np.clip(np.full(count, cap/fd), .001*h, .45*h) for cap in capacities]
    for i in range(4):
        d = h-steel.centre[i]
        radicand = d*d-2*wa[:, i]*1000/fd
        target = d-np.sqrt(np.maximum(radicand, 0))
        candidate_depths.append(np.clip(target, .001*h, .45*h))
    for a in candidate_depths:
        zt, zb = h/2-a/2, -h/2+a/2
        qt = (k12-zb*n12)/(zt-zb)
        qb = n12-qt
        dt, db = abs(qt), abs(qb)
        x = _uniaxial_fields(n1, k1, dt, db, zt, zb, zs[:,0], zs[:,1], capacities[0], capacities[1])
        y = _uniaxial_fields(n2, k2, dt, db, zt, zb, zs[:,2], zs[:,3], capacities[2], capacities[3])
        cx_t, cx_b, sx_t, sx_b, vx = (value[:, None, :] for value in x)
        cy_t, cy_b, sy_t, sy_b, vy = (value[None, :, :] for value in y)
        ct = principal_max(cx_t+dt, cy_t+dt, qt)
        cb = principal_max(cx_b+db, cy_b+db, qb)
        concrete_dc = np.maximum(ct, cb)/(fd*a)
        steel_dc = np.maximum(np.maximum(sx_t/capacities[0], sx_b/capacities[1]),
                              np.maximum(sy_t/capacities[2], sy_b/capacities[3]))
        score = np.maximum.reduce([np.broadcast_to(steel_dc, concrete_dc.shape), concrete_dc,
            np.broadcast_to(min_dc, concrete_dc.shape), np.broadcast_to(spacing_dc, concrete_dc.shape)])
        score = np.where(vx & vy, score, np.inf)
        combinations = len(x[0])*len(y[0])
        choice = score.reshape(combinations, count).argmin(axis=0)
        row_score = score.reshape(combinations, count)[choice, np.arange(count)]
        improved = (row_score < best) & np.isfinite(row_score)
        if not improved.any():
            continue
        xi, yi = choice//len(y[0]), choice%len(y[0])
        ix = np.arange(count)
        selected = np.column_stack((a, qt, qb, x[0][xi,ix], x[1][xi,ix], y[0][yi,ix], y[1][yi,ix],
            x[2][xi,ix], x[3][xi,ix], y[2][yi,ix], y[3][yi,ix],
            concrete_dc.reshape(combinations,count)[choice,ix]))
        fields[improved] = selected[improved]
        best[improved] = row_score[improved]
    if not np.isfinite(best).all():
        raise ValueError("No finite equilibrated sandwich field found for one or more source rows")
    shear_dc, qualified, dv, beta, eps, shear_capacity = _shear(h, v, steel, max_m, max_n)
    # The overall number is the maximum KNOWN component ratio. It is not an
    # interaction ratio. Missing applicability stays NaN and never means zero.
    known_dc = np.fmax(best, shear_dc)
    output = {"Field D/C": known_dc, "N–M field D/C": best,
        "N–M field status": np.where(best>1+1e-8, "Preview FAIL", "Preview PASS"),
        "Combined N–M–V status": np.where(v>1e-12, "REVIEW", "Not required (V=0)"),
        "Shrinkage D/C": min_dc, "Spacing D/C": spacing_dc,
        "Face depth (mm)": fields[:,0], "q top (N/mm)": fields[:,1], "q bottom (N/mm)": fields[:,2],
        "Cx top (N/mm)": fields[:,3], "Cx bottom (N/mm)": fields[:,4],
        "Cy top (N/mm)": fields[:,5], "Cy bottom (N/mm)": fields[:,6],
        "Concrete D/C": fields[:,11], "Shear D/C": shear_dc, "Shear dv (mm)": dv,
        "Shear beta": beta, "Shear strain bound": eps,
        "Shear status": np.where(~qualified, "REVIEW", np.where(shear_dc>1+1e-8, "Preview FAIL", "Preview PASS")),
        "Shear phiVc (kN/m)": np.where(qualified, shear_capacity, np.nan)}
    for i, group in enumerate(GROUPS):
        tensile = fields[:,7+i]
        output[group+" force (N/mm)"] = tensile
        output[group+" Strength D/C"] = tensile/capacities[i]
        required = np.maximum(tensile*1000/(PHI_TIE*steel.fy[i]), shrinkage[:,i])
        output[group+" As required (mm²/m)"] = required
        output[group+" D/C"] = required/steel.area[i]
        output[group+" WA (kN·m/m)"] = wa[:,i]
    # Reconstruct all six resultants independently from the selected field.
    a, qt, qb = fields[:,:3].T
    zt, zb = h/2-a/2, -h/2+a/2
    cxt, cxb, cyt, cyb = fields[:,3:7].T
    tx_t, tx_b, ty_t, ty_b = fields[:,7:11].T
    rebuilt_n = np.column_stack((tx_t+tx_b-cxt-cxb-abs(qt)-abs(qb),
        ty_t+ty_b-cyt-cyb-abs(qt)-abs(qb), qt+qb))
    rebuilt_k = np.column_stack((zs[:,0]*tx_t+zs[:,1]*tx_b-zt*(cxt+abs(qt))-zb*(cxb+abs(qb)),
        zs[:,2]*ty_t+zs[:,3]*ty_b-zt*(cyt+abs(qt))-zb*(cyb+abs(qb)), zt*qt+zb*qb))
    residuals = np.column_stack((rebuilt_n-membrane, -rebuilt_k/1000-moment))
    scale = np.maximum(1, abs(np.column_stack((membrane, moment))))
    output["Equilibrium residual"] = np.max(abs(residuals)/scale, axis=1)
    if np.max(output["Equilibrium residual"]) > 1e-7:
        raise ValueError("Six-component equilibrium tolerance exceeded; results are not accepted")
    output["Status"] = np.where(known_dc>1+1e-8, "Preview FAIL",
        np.where(~qualified | (v>1e-12), "REVIEW", "Preview PASS"))
    return pd.DataFrame(output)


def calculate(state, *, progress=None, chunk_size=2048):
    package = current_package(state)
    if package is None:
        raise ValueError("Import the complete current shell package first")
    signature = fingerprint(state)
    steel = steel_from_state(state)
    start = time.monotonic()
    geometry = recover(package)
    forces = package.tables["forces"]
    ids = set(geometry.corners["Area"])
    frame = forces.loc[forces["Area"].isin(ids)].copy().reset_index(drop=True)
    frame = frame.merge(geometry.corners, on=["Area", "AreaElem", "Joint"], how="left", validate="many_to_one")
    if frame["Thickness (mm)"].isna().any():
        raise ValueError("Missing recovered thickness at a force-record corner")
    frame = steel_axis_forces(frame, geometry.parent_axes)
    connections = connection_layout(package, geometry, state)
    frame = annotate_connections(frame, connections)
    nominal = frame.loc[frame[INCLUDED]]
    if nominal.empty:
        raise ValueError("No nominal slab nodes remain outside the excluded connection lines / bearing end zones; no design D/C is available")
    parts = []
    for begin in range(0, len(nominal), chunk_size):
        part = nominal.iloc[begin:begin+chunk_size]
        checks = section_check(part["Thickness (mm)"].to_numpy(), part[["Nx","Ny","Nxy"]].to_numpy(),
            part[["Mx","My","Mxy"]].to_numpy(), part[["Vx","Vy"]].to_numpy(), steel)
        checks.index = part.index
        parts.append(checks)
        if progress:
            progress(min(begin+chunk_size,len(nominal)), len(nominal))
    checked = pd.concat(parts).reindex(frame.index)
    all_rows = pd.concat((frame.reset_index(drop=True), checked), axis=1)
    from concrete_pmm_pro.analysis.slab_code57 import strip_references, controlling_checks, check_breakdown
    references = strip_references(nominal['Thickness (mm)'].to_numpy(), nominal[['Nx','Ny','Nxy']].to_numpy(),
        nominal[['Mx','My','Mxy']].to_numpy(), steel)
    references.index = nominal.index
    all_rows = pd.concat((all_rows, references.reindex(frame.index)), axis=1)
    all_rows['Controlling check'] = controlling_checks(all_rows)
    excluded = ~all_rows[INCLUDED]
    all_rows.loc[excluded, 'Controlling check'] = 'Excluded node'
    for column in ('Status', 'N–M field status', 'Shear status', 'Combined N–M–V status',
                   'Code flexure reference status', 'Minimum sufficient screen status'):
        all_rows.loc[excluded, column] = 'EXCLUDED'
    all_rows.loc[excluded, 'Code reference reason'] = 'Node excluded from nominal slab design'
    design = all_rows.loc[all_rows[INCLUDED]]
    step_keys = [c for c in ("OutputCase", "StepType", "StepNum") if c in all_rows]
    coverage = all_rows.groupby(step_keys, dropna=False).size().reset_index(name="Imported records")
    nominal_counts = all_rows.groupby(step_keys, dropna=False)[INCLUDED].agg(['sum', 'count']).reset_index()
    coverage['Nominal design records'] = nominal_counts['sum'].to_numpy()
    coverage['Excluded records'] = (nominal_counts['count']-nominal_counts['sum']).to_numpy()
    coverage["Expected corner records"] = len(geometry.corners)
    coverage["Missing records"] = coverage["Expected corner records"]-coverage["Imported records"]
    incomplete = coverage["Missing records"].gt(0).any()
    summary = []
    for group, area in zip(GROUPS, steel.area):
        key = group+" As required (mm²/m)"
        row = design.loc[(design[key]/area).idxmax()]
        summary.append({"Reinforcement": group, "As provided (mm²/m)": area, "As required (mm²/m)": row[key],
            "D/C": row[key]/area, "Case": row["OutputCase"], "Step": row["StepType"],
            "X (m)": row["X (m)"], "Y (m)": row["Y (m)"], "AreaElem": row["AreaElem"], "Joint": row["Joint"],
            "Status": "Preview FAIL" if row[key]/area>1+1e-8 else "REVIEW" if incomplete else "Preview PASS"})
    governing = design.loc[design["Field D/C"].idxmax()]
    nm_governing = design.loc[design["N–M field D/C"].idxmax()]
    statuses = design["Status"].value_counts().to_dict()
    status = "Preview FAIL" if statuses.get("Preview FAIL") else "REVIEW" if statuses.get("REVIEW") or incomplete else "Preview PASS"
    result = {"version": VERSION, "fingerprint": signature, "rows": all_rows, "summary": pd.DataFrame(summary),
        "governing": governing.to_dict(), "nm_governing": nm_governing.to_dict(),
        "status": status, "counts": statuses, "geometry": geometry,
        "steel": steel, "scope": SCOPE, "seconds": time.monotonic()-start,
        "source_rows": len(frame), "design_rows": len(design), "excluded_rows": int(excluded.sum()),
        "excluded_nodes": int(all_rows.loc[excluded, 'Joint'].nunique()),
        "bearing_excluded_rows": int(all_rows['Bearing end-zone'].ne('').sum()),
        "bearing_excluded_nodes": int(all_rows.loc[all_rows['Bearing end-zone'].ne(''), 'Joint'].nunique()),
        "connections": connections,
        "coverage": coverage, "incomplete": bool(incomplete),
        "code": workflow_project_code_label_from_session(state)}
    result['check_summary'] = check_breakdown(design)
    result['reference_counts'] = design['Minimum sufficient screen status'].value_counts().to_dict()
    result['seconds'] = time.monotonic()-start
    return result
