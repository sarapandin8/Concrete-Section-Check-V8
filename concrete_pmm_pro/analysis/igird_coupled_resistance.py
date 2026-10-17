"""COUPLED34: research-only closed-cell / interface resource model.

This is an idealized fixed-angle, fully cracked space-truss resistance model,
NOT a validated full-composite concrete design method. It deliberately has
no Vc, cohesion, dowel bending or additive Tn credit. One physical U-leg force
must satisfy the transverse truss demand AND the joint normal/friction
equilibrium. A signed longitudinal friction couple is retained: pure torque
does not become a zero interface demand when the net longitudinal shear is 0.

Units throughout: N, mm, MPa; interface forces per mm of member length.
The contact is discretized; its friction cone is an INSCRIBED regular polygon.
LP equilibrium/yield verification is software verification, not evidence of
strain compatibility, realistic cracking or experimental structural validation.
Production acceptance is deliberately unavailable in this model version.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np
from scipy.optimize import linprog

VERSION = "IGIRDER.COUPLED34"
MODEL = "Fixed-angle cracked closed-cell + shared U-leg/contact equilibrium"
PRODUCTION_VALIDATED = False
LIMITATIONS = (
    "Candidate closed path must be verified on the actual cage; 90-degree U hooks alone do not establish closure.",
    "Fixed 45-degree truss, zero Vc and cohesion; diagonal concrete cap is a model assumption, not a calibrated MCFT law.",
    "No slip/opening or section strain compatibility; splitting, nodal zones, slab transverse bending and lap stress transfer are unverified.",
    "No experimental validation of this composite girder/slab/dowel system; production resistance is withheld.",
)


@dataclass(frozen=True)
class Cell:
    ao_mm2: float
    ph_mm: float
    dv_mm: float
    contact_width_mm: float
    leg_spacing_mm: float
    girder_leg_N_per_mm: float
    dowel_leg_N_per_mm: float
    closure_N_per_mm: float
    longitudinal_N: float
    diagonal_q_N_per_mm: float
    mu: float
    contact_MPa: float
    interface_MPa: float
    cot_theta: float = 1.0

    def validate(self):
        supplies = {"girder_leg_N_per_mm", "dowel_leg_N_per_mm", "closure_N_per_mm", "longitudinal_N", "diagonal_q_N_per_mm"}
        if any(isinstance(v, bool) or not math.isfinite(v) or (v < 0 if k in supplies else v <= 0)
               for k,v in asdict(self).items()):
            raise ValueError("Closed-cell geometry/friction must be positive; resistance supplies must be nonnegative and finite.")
        if self.leg_spacing_mm >= self.contact_width_mm:
            raise ValueError("The two U-leg centres must lie strictly inside the contact strip.")
        if not 0.5 <= self.cot_theta <= 2.0:
            raise ValueError("Research truss cot(theta) is outside the supported range 0.5–2.")


@dataclass(frozen=True)
class Actions:
    vu_N: float
    tu_Nmm: float
    mu_Nmm: float = 0.0
    nu_tension_N: float = 0.0
    qx_N_per_mm: float = 0.0
    qy_N_per_mm: float = 0.0
    opening_N_per_mm: float = 0.0
    roll_Nmm_per_mm: float = 0.0
    # Background in-plane moment of longitudinal interface tractions, about z.
    # The torque-induced signed couple is added separately, never lost by |sum q|.
    mz_Nmm_per_mm: float = 0.0

    def validate(self):
        if any(isinstance(v, bool) or not math.isfinite(v) for v in asdict(self).values()):
            raise ValueError("All concurrent section and interface actions must be explicit finite values.")


def solve(cell: Cell, actions: Actions, *, nominal=True, cells=32, rays=8) -> dict:
    """Scale V/T and interface actions together; hold M/N fixed.

    Model factors when nominal=False: steel=.90, concrete contact/diagonal=.70,
    interface shear=.90. They are explicitly model factors, not certification
    of the composite method. Pure model Tn uses all factors=1 and zero M/N/V.

    At fixed angle and Vc=0, Vs=Vu/phi is carried by the same two physical legs.
    The concurrent longitudinal screen is the solid-section 5.7.3.6.3-1 force
    form, not an independent Al reserve added to flexural steel.
    """
    cell.validate(); actions.validate()
    if isinstance(cells, bool) or not isinstance(cells, int) or not 8 <= cells <= 256:
        raise ValueError("Use 8–256 contact strips.")
    if isinstance(rays, bool) or not isinstance(rays, int) or not 8 <= rays <= 32 or rays % 4:
        raise ValueError("Use 8, 12, ... 32 inscribed friction directions.")
    sf, cf, jf = (1., 1., 1.) if nominal else (.90, .70, .90)
    # Work with nominal-equivalent actions for the global truss and keep the
    # actual joint actions unchanged: model resistance factors act on supplies.
    qv = abs(actions.vu_N) / (2. * cell.dv_mm)
    qt = actions.tu_Nmm / (2. * cell.ao_mm2)
    truss = (qv + abs(qt)) / cell.cot_theta
    tor_tie = abs(qt) / cell.cot_theta
    long_base = max(0., abs(actions.mu_Nmm) / cell.dv_mm + .5 * actions.nu_tension_N)
    long_increment = cell.cot_theta * math.hypot(.5 * abs(actions.vu_N), .45 * cell.ph_mm * qt)
    steel_g = sf * cell.girder_leg_N_per_mm
    steel_d = sf * cell.dowel_leg_N_per_mm
    steel_c = sf * cell.closure_N_per_mm
    long_cap = sf * cell.longitudinal_N
    if long_base > long_cap + 1e-8:
        return _blocked("Fixed M/N already exceeds the supplied longitudinal model resistance.", status="MODEL EXCEEDED")
    if max(qv, abs(qt), abs(actions.qx_N_per_mm), abs(actions.qy_N_per_mm),
           abs(actions.opening_N_per_mm), abs(actions.roll_Nmm_per_mm), abs(actions.mz_Nmm_per_mm)) <= 1e-14:
        return {"version": VERSION, "ready": True, "model_status": "ZERO SCALED ACTIONS", "capacity_factor": None,
                "utilization": 0., "production_status": "UNVALIDATED — REVIEW", "accepted_phiTn_Nmm": None,
                "accepted_VT_factor": None, "nominal": nominal, "limitations": list(LIMITATIONS)}
    b, a = cell.contact_width_mm, cell.leg_spacing_mm
    dx = b / cells
    y = np.linspace(-b/2 + dx/2, b/2 - dx/2, cells)
    angles = np.arange(rays) * 2. * math.pi / rays
    ux, uy = np.cos(angles), np.sin(angles)
    # Unknowns: T_left, T_right, C_j, directional nonnegative friction rays, lambda.
    contact = 2
    fric = contact + cells
    size = fric + cells * rays + 1
    scale_m = b / 2.
    eq = np.zeros((5, size))
    rhs = np.zeros(5)
    eq[0,:2] = 1.; eq[0,contact:fric] = -1.; eq[0,-1] = -actions.opening_N_per_mm
    eq[1,:2] = [-a/b, a/b]; eq[1,contact:fric] = -y/scale_m
    eq[1,-1] = -actions.roll_Nmm_per_mm/scale_m
    for j in range(cells):
        sl = slice(fric+j*rays, fric+(j+1)*rays)
        eq[2,sl] = ux; eq[3,sl] = uy
        eq[4,sl] = -y[j]*ux/scale_m
    eq[2,-1] = -actions.qx_N_per_mm
    eq[3,-1] = -actions.qy_N_per_mm
    # Interface traction moment Mz = -sum(y*qx). Torque circulation gives
    # qx(left)=+qt, qx(right)=-qt -> Mz=+a*qt. This is NOT interface roll mx.
    eq[4,-1] = -(actions.mz_Nmm_per_mm + a*qt)/scale_m
    inequalities, limits, labels = [], [], []
    def upper(coeff, bound, label):
        row = np.zeros(size)
        for idx, value in coeff.items(): row[idx] = value
        inequalities.append(row); limits.append(bound); labels.append(label)
    for j in range(cells):
        sl = range(fric+j*rays, fric+(j+1)*rays)
        upper({**{i:1. for i in sl}, contact+j:-cell.mu}, 0., f"friction cone {j}")
        upper({i:1. for i in sl}, jf*cell.interface_MPa*dx, f"interface concrete {j}")
    # Externally imposed compression is not silently credited as Pc.
    upper({0:-cell.mu, 1:-cell.mu, **{i:1. for i in range(fric,size-1)}}, 0., "shared tie clamping")
    # SAME T_i, never a second copy of the dowel supply for the truss.
    for i in (0,1): upper({i:-1., size-1:truss}, 0., f"U-leg {i} truss allocation")
    upper({size-1:truss}, steel_g, "girder leg")
    upper({size-1:tor_tie}, steel_c, "slab closing tie")
    upper({size-1:qv+abs(qt)}, cf*cell.diagonal_q_N_per_mm, "diagonal concrete model")
    upper({size-1:long_increment}, max(0.,long_cap-long_base), "shared longitudinal steel")
    A, z = np.array(inequalities), np.array(limits)
    bounds = [(0.,steel_d)]*2 + [(0.,cf*cell.contact_MPa*dx)]*cells + [(0.,None)]*(cells*rays+1)
    objective = np.zeros(size); objective[-1] = -1.
    result = linprog(objective, A_ub=A, b_ub=z, A_eq=eq, b_eq=rhs, bounds=bounds, method="highs")
    if not result.success or result.status != 0 or result.x is None:
        return _blocked("Coupled equilibrium has no verified optimum: " + str(result.message))
    values = result.x
    residual = float(np.max(np.abs(eq@values-rhs)))
    violation = max(0., float(np.max(A@values-z)), -float(np.min(values)),
                    max(float(v)-hi for v,(_,hi) in zip(values,bounds) if hi is not None))
    # Independently test dual optimality; an equilibrium-only feasible result
    # cannot be reported as a radial resistance maximum.
    gap = abs(float(objective@values) - float(z@result.ineqlin.marginals +
        sum(hi*dual for (_,hi),dual in zip(bounds,result.upper.marginals) if hi is not None)))
    eq_relative = float(np.max(np.abs(eq@values-rhs) / np.maximum(1., np.abs(eq)@np.abs(values)+np.abs(rhs))))
    ub_relative = float(np.max(np.maximum(0.,A@values-z) / np.maximum(1., np.abs(A)@np.abs(values)+np.abs(z))))
    bound_relative = max([0., max(-float(v)/max(1.,abs(float(v))) for v in values)] +
                         [max(0.,float(v)-hi)/max(1.,abs(hi)) for v,(_,hi) in zip(values,bounds) if hi is not None])
    dual_relative = gap / max(1.,abs(float(objective@values)))
    if not np.isfinite(values).all() or max(eq_relative,ub_relative,bound_relative,dual_relative) > 1e-7:
        return _blocked("Coupled equilibrium, capacity bounds or LP duality residual exceeds tolerance.")
    lam = max(0.,float(values[-1])); force = values[fric:-1].reshape(cells,rays)
    sx, sy = force@ux, force@uy
    active = [labels[i] for i,slack in enumerate(z-A@values) if abs(slack) <= 1e-7*max(1.,abs(z[i])) and abs(result.ineqlin.marginals[i]) > 1e-10]
    if any(abs(values[i]-steel_d) <= 1e-7*max(1.,steel_d) and abs(result.upper.marginals[i]) > 1e-10 for i in (0,1)):
        active.append("shared U-dowel capacity")
    return {"version": VERSION, "model": MODEL, "ready": True, "nominal": nominal,
        "model_status": "WITHIN MODEL" if lam >= 1.-1e-7 else "MODEL EXCEEDED",
        "capacity_factor": lam, "utilization": (1./lam if lam > 1e-12 else None),
        "production_status": "UNVALIDATED — REVIEW", "accepted_phiTn_Nmm": None, "accepted_VT_factor": None,
        "active_limits": active, "fixed_MN_longitudinal_N": long_base,
        "longitudinal_increment_N": long_increment*lam,
        "truss_force_each_N_per_mm": truss*lam,
        "tie_cap_each_N_per_mm": steel_d, "tie_forces_N_per_mm": values[:2].tolist(),
        "contact_y_mm": y.tolist(), "contact_forces_N_per_mm": values[contact:fric].tolist(),
        "friction_x_N_per_mm": sx.tolist(), "friction_y_N_per_mm": sy.tolist(),
        "normal_rebuilt_N_per_mm": float(values[:2].sum()-values[contact:fric].sum()),
        "roll_rebuilt_Nmm_per_mm": float(np.dot([-a/2,a/2],values[:2])-np.dot(y,values[contact:fric])),
        "qx_rebuilt_N_per_mm": float(sx.sum()), "qy_rebuilt_N_per_mm": float(sy.sum()),
        "mz_rebuilt_Nmm_per_mm": float(-y@sx), "torque_flow_q_N_per_mm": qt*lam,
        "equilibrium_residual": residual, "inequality_violation": violation, "duality_gap": gap,
        "equilibrium_relative":eq_relative,"inequality_relative":ub_relative,"bounds_relative":bound_relative,"duality_relative":dual_relative,
        "contact_cells": cells, "friction_rays": rays, "friction_cone": "INSCRIBED",
        "factors": {"steel":sf,"contact_and_diagonal":cf,"interface":jf},
        "cell": asdict(cell), "actions": asdict(actions), "limitations": list(LIMITATIONS)}


def _blocked(reason, *, status="MODEL BLOCKED"):
    return {"version":VERSION,"ready":False,"model_status":status,"reason":reason,
            "production_status":"UNVALIDATED — REVIEW", "accepted_phiTn_Nmm":None,"accepted_VT_factor":None}


def nominal_torsion(cell: Cell, *, cells=32):
    result = solve(cell, Actions(vu_N=0., tu_Nmm=1.e6), nominal=True, cells=cells)
    return {**result, "model_Tn_Nmm": result["capacity_factor"]*1.e6 if result.get("ready") and result.get("capacity_factor") is not None else None,
            "capacity_definition":"Nominal pure torsion of the idealized closed-cell system; V=M=N=external joint loads=0. Not conditional resistance at the actual M/N."}


def validation_table():
    """Capabilities, not user checkboxes capable of overriding model validation."""
    return [
        {"Validation":"Shared resources / signed interface equilibrium", "Status":"IMPLEMENTED", "Evidence":"One T_i variable; 5 joint equilibrium equations; independent residual and LP duality checks"},
        {"Validation":"Analytical limiting cases / mesh sensitivity", "Status":"SEE RELEASE TEST RECORD", "Evidence":"Pure T/V; closure/longitudinal/diagonal limits; friction couple; contact refinement; no double counting"},
        {"Validation":"Closed cage / 135-degree hooks / lap and anchorage", "Status":"PROJECT DETAIL REQUIRED", "Evidence":"90-degree tension-hook development is not a closed torsion cage validation"},
        {"Validation":"Crack, slip and strain compatibility", "Status":"NOT VALIDATED", "Evidence":"No calibrated nonlinear composite constitutive / compatibility model in COUPLED34"},
        {"Validation":"Independent physical structural validation", "Status":"NOT VALIDATED", "Evidence":"Published monolithic tests do not validate this girder/slab/U-dowel assembly"},
        {"Validation":"Production full composite Tn / V–T", "Status":"WITHHELD", "Evidence":"No checkbox, uploaded label or numerical LP pass can enable design acceptance"},
    ]
