"""Explicit two-path V/T reinforcement calculation, for engineering review.

This fixed-angle, fully cracked space-truss idealization is NOT a validated
full-composite design method. It computes nominal V and T intercepts and a
concurrent V/T load factor. The original I-hoop and the candidate U/slab path
have distinct areas; neither two U legs nor independent Tn values are added
to an existing closed-hoop At. One pair of U forces supplies its web truss
AND friction clamping. The actual longitudinal pools are shared by both paths.

The proposed U-to-slab closure is a structural HYPOTHESIS. Hook development
does not prove it. Numerical equilibrium/duality is software verification.
No result from this module may replace a production resistance or PASS.
Units: N, mm, MPa. q and interface resultants are per mm along the girder.
"""
from dataclasses import asdict, dataclass, replace
from copy import deepcopy
import math

import numpy as np
from scipy.optimize import linprog

VERSION = "IGIRDER.COMPOSITE51.anchorage-trace.CSITU46"
LIMITATIONS = [
    "Fixed-angle fully cracked truss, zero Vc/cohesion; not a calibrated MCFT or strain/slip-compatible section model.",
    "U-cell closure through the slab mats/anchorage zone is a hypothesis; 90-degree hooks and tied mesh do not establish a code-qualified closed torsion cage.",
    "Shared concrete-flow and top/bottom longitudinal bounds are declared model constraints, not experimental structural validation.",
    "V2 and reported CSI T are scaled; M3/N retain the bending-reader basis. Tu is not shifted to the I-centroid. M2/V3 full resistance and the source-point coupled resistance remain unvalidated.",
    "The app uses qx=(VI+VU)/d_interface, with the separate girder/slab lever arm. This is a conservative flexural-shear approximation, not recovered CSI Beam/Slab reactions or a validated full torsion-interface field.",
    "Deck longitudinal credit is conditional on continuous bars within the entered start/end interval; existing unconfirmed drawing flags are preserved, not silently approved.",
]


@dataclass(frozen=True)
class Supplies:
    core_ao_mm2: float
    core_ph_mm: float
    core_dv_mm: float
    core_leg_N_per_mm: float
    u_ao_mm2: float
    u_ph_mm: float
    u_dv_mm: float
    u_leg_N_per_mm: float
    slab_closing_N_per_mm: float
    bottom_longitudinal_N: float
    top_longitudinal_N: float
    top_girder_longitudinal_N: float
    top_slab_longitudinal_N: float
    diagonal_q_N_per_mm: float
    contact_width_mm: float
    u_leg_spacing_mm: float
    contact_MPa: float
    interface_MPa: float
    mu: float
    cot_theta: float
    # None retains the isolated legacy branch model for external callers and
    # old unit fixtures. The application must supply an explicit interface
    # lever arm; it must never silently fall back to the web shear depth.
    interface_dv_mm: float | None = None

    def validate(self):
        zeros = {"core_leg_N_per_mm", "u_leg_N_per_mm", "slab_closing_N_per_mm",
            "bottom_longitudinal_N", "top_longitudinal_N", "top_girder_longitudinal_N",
            "top_slab_longitudinal_N", "diagonal_q_N_per_mm", "mu"}
        for key, value in asdict(self).items():
            if key == "interface_dv_mm" and value is None:
                continue
            if isinstance(value, bool) or not math.isfinite(value) or (value < 0 if key in zeros else value <= 0):
                raise ValueError("Invalid composite supply: " + key)
        if self.u_leg_spacing_mm >= self.contact_width_mm:
            raise ValueError("U-leg centres must lie inside the actual interface width.")
        if not .5 <= self.cot_theta <= 2.:
            raise ValueError("The review truss supports 0.5 <= cot(theta) <= 2 only.")
        if not math.isclose(self.top_longitudinal_N,self.top_girder_longitudinal_N+self.top_slab_longitudinal_N,rel_tol=1e-9,abs_tol=1e-6):
            raise ValueError("Upper longitudinal total must reconcile to distinct girder and slab inventories.")


def solve(s: Supplies, *, vu_N, tu_Nmm, mu_Nmm=0., nu_tension_N=0., cells=16):
    """Maximum radial factor on V2/T, holding M3/N. No strength factors inferred.

    Same-signed torque circulation in the two paths is a declared restriction.
    Longitudinal bounds use |V|/2 + .45 sum(ph*q), a conservative L1 bound
    on the solid-section L2 increment. Concrete has ONE shared flow budget.
    This is a conditional mechanical model, not a code resistance envelope.
    """
    s.validate()
    if any(isinstance(v, bool) or not math.isfinite(v) for v in (vu_N, tu_Nmm, mu_Nmm, nu_tension_N)):
        raise ValueError("Finite concurrent actions required; unknown is not zero.")
    if not isinstance(cells, int) or isinstance(cells, bool) or not 8 <= cells <= 128:
        raise ValueError("Use 8-128 contact strips.")
    v, torque = abs(vu_N), abs(tu_Nmm)
    base = {"version": VERSION, "accepted_Vn_kN": None, "accepted_Tn_kNm": None,
        "accepted_VT_factor": None, "production_status": "UNVALIDATED — REVIEW"}
    if max(v, torque) <= 1e-12:
        return {**base, "ready": True, "capacity_factor": None, "utilization": 0., "status": "ZERO RAY"}
    # v0,v1,q0,q1,tL,tR,C_j,Sx_j,lambda. q1 >=0; Sx_j is signed.
    size = 7 + 2*cells
    ci, si, li = 6, 6+cells, size-1
    b = s.contact_width_mm
    dy = b/cells
    y = np.linspace(-b/2+dy/2, b/2-dy/2, cells)
    eq, rhs = [], []
    def balance(items):
        row = np.zeros(size)
        for key, val in items.items(): row[key] = val
        eq.append(row); rhs.append(0.)
    balance({0:1., 1:1., li:-v})
    balance({2:2*s.core_ao_mm2/b, 3:2*s.u_ao_mm2/b, li:-torque/b})
    balance({4:1., 5:1., **{ci+j:-1. for j in range(cells)}})
    balance({4:-s.u_leg_spacing_mm/b, 5:s.u_leg_spacing_mm/b,
        **{ci+j:-2*y[j]/b for j in range(cells)}})
    # Using the slab to establish composite flexural depth requires checking
    # longitudinal shear transfer for the WHOLE V resultant, not just VU.
    # AASHTO 5.7.4.5 defines its own lever arm to slab mid-depth. Keep the
    # already declared U torsion couple; this is still a model hypothesis.
    if s.interface_dv_mm is not None:
        balance({**{si+j:1. for j in range(cells)},
            0:-1/s.interface_dv_mm, 1:-1/s.interface_dv_mm})
    else:
        balance({**{si+j:1. for j in range(cells)}, 1:-1/s.u_dv_mm})
    # Opposing torsion-induced interface tractions retain a nonzero moment.
    balance({**{si+j:-y[j]/b for j in range(cells)}, 3:-s.u_leg_spacing_mm/b})
    ub, limits, labels = [], [], []
    def upper(items, limit, label):
        row = np.zeros(size)
        for key, val in items.items(): row[key] = val
        ub.append(row); limits.append(limit); labels.append(label)
    cot = s.cot_theta
    upper({0:1/(2*s.core_dv_mm*cot), 2:1/cot}, s.core_leg_N_per_mm, "I-girder closed-hoop leg")
    for side in (4,5):
        upper({1:1/(2*s.u_dv_mm*cot), 3:1/cot, side:-1.}, 0., "same U leg supplies V/T and clamping")
    upper({3:1/cot}, s.slab_closing_N_per_mm, "slab transverse closure")
    upper({0:1/(2*s.core_dv_mm), 1:1/(2*s.u_dv_mm), 2:1., 3:1.},
        s.diagonal_q_N_per_mm, "shared concrete flow budget")
    held = mu_Nmm/s.u_dv_mm
    for name, long_cap, bending in [("bottom",s.bottom_longitudinal_N,held), ("top",s.top_longitudinal_N,-held)]:
        reserve = long_cap - bending - .5*nu_tension_N
        if reserve < -1e-8:
            return {**base,"ready":False,"status":"FIXED M/N EXCEEDS LONGITUDINAL MODEL", "reason":name+" longitudinal pool exhausted"}
        upper({0:.5*cot, 1:.5*cot, 2:.45*s.core_ph_mm*cot, 3:.45*s.u_ph_mm*cot},
            max(0.,reserve), name+" shared longitudinal steel")
    # Slab steel cannot reinforce the I-only path when its U connection is
    # absent. These additional bounds prevent a disconnected slab from
    # becoming an invisible longitudinal reserve for the core.
    core_top_reserve = s.top_girder_longitudinal_N + held - .5*nu_tension_N
    if core_top_reserve < -1e-8:
        return {**base,"ready":False,"status":"FIXED M/N EXCEEDS LONGITUDINAL MODEL","reason":"core upper pool exhausted"}
    upper({0:.5*cot, 2:.45*s.core_ph_mm*cot},max(0.,core_top_reserve),"I-path upper longitudinal steel")
    upper({1:.5*cot, 3:.45*s.u_ph_mm*cot},s.top_slab_longitudinal_N,"U-path slab longitudinal steel")
    for j in range(cells):
        upper({si+j:1., ci+j:-s.mu},0.,"interface friction +")
        upper({si+j:-1., ci+j:-s.mu},0.,"interface friction -")
    bounds = [(0.,None)]*4 + [(0.,s.u_leg_N_per_mm)]*2 + [(0.,s.contact_MPa*dy)]*cells
    bounds += [(-s.interface_MPa*dy,s.interface_MPa*dy)]*cells + [(0.,None)]
    A, z, E, r = np.asarray(ub), np.asarray(limits), np.asarray(eq), np.asarray(rhs)
    # N variables are used consistently; row scaling preserves the domain.
    escale = np.maximum(1.,np.max(abs(E),axis=1)); uscale = np.maximum(1.,np.max(abs(A),axis=1))
    E, r = E/escale[:,None], r/escale
    A, z = A/uscale[:,None], z/uscale
    objective = np.zeros(size); objective[-1] = -1.
    fit = linprog(objective,A_ub=A,b_ub=z,A_eq=E,b_eq=r,bounds=bounds,method="highs")
    if not fit.success:
        return {**base,"ready":False,"status":"MODEL BLOCKED","reason":str(fit.message)}
    f = fit.x
    eq_err = float(np.max(abs(E@f-r)/np.maximum(1.,abs(E)@abs(f)+abs(r))))
    ub_err = float(np.max(np.maximum(0.,A@f-z)/np.maximum(1.,abs(A)@abs(f)+abs(z))))
    bound_err = max([0.] + [max(0.,lo-val)/max(1.,abs(lo)) for val,(lo,hi) in zip(f,bounds) if lo is not None]
        + [max(0.,val-hi)/max(1.,abs(hi)) for val,(lo,hi) in zip(f,bounds) if hi is not None])
    dual = float(z@fit.ineqlin.marginals+r@fit.eqlin.marginals)
    for (lo,hi),dl,dh in zip(bounds,fit.lower.marginals,fit.upper.marginals):
        if lo is not None: dual += lo*dl
        if hi is not None: dual += hi*dh
    gap = abs(float(objective@f)-dual)/max(1.,abs(float(objective@f)))
    stationarity = E.T@fit.eqlin.marginals+A.T@fit.ineqlin.marginals+fit.lower.marginals+fit.upper.marginals
    stationarity_err = float(np.max(abs(objective-stationarity)/np.maximum(1.,abs(objective)+abs(stationarity))))
    verified = np.isfinite(f).all() and max(eq_err,ub_err,bound_err,gap,stationarity_err) < 2e-7
    if not verified:
        return {**base,"ready":False,"status":"NUMERICAL VERIFICATION FAILED"}
    lam = max(0.,float(f[-1]))
    active = [labels[i] for i,slack in enumerate(z-A@f) if abs(slack)<1e-6*max(1.,abs(z[i])) and abs(fit.ineqlin.marginals[i])>1e-10]
    if any(abs(f[k]-s.u_leg_N_per_mm)<1e-6*max(1.,s.u_leg_N_per_mm) for k in (4,5)):
        active.append("U-leg physical force ceiling")
    return {**base,"ready":True,"status":"MODEL REVIEW", "capacity_factor":lam,
        "utilization":1/lam if lam>1e-12 else None, "capacity_exhausted":lam<=1e-12,
        "active_limits":list(dict.fromkeys(active)),
        "core_V_N":float(f[0]),"U_V_N":float(f[1]),
        "core_T_Nmm":float(2*s.core_ao_mm2*f[2]),"U_T_Nmm":float(2*s.u_ao_mm2*f[3]),
        "U_force_each_N_per_mm":f[4:6].tolist(),"contact_y_mm":y.tolist(),
        "contact_compression_N_per_mm":f[ci:si].tolist(),"contact_qx_N_per_mm":f[si:li].tolist(),
        "interface_flow_basis":"WHOLE COMPOSITE V / d_interface" if s.interface_dv_mm is not None else "LEGACY U-BRANCH ONLY",
        "interface_dv_mm":s.interface_dv_mm,
        "interface_required_qx_N_per_mm":float((f[0]+f[1])/s.interface_dv_mm if s.interface_dv_mm is not None else f[1]/s.u_dv_mm),
        "checks":{"equilibrium_relative":eq_err,"resource_relative":ub_err,"bound_relative":bound_err,
            "duality_relative":gap,"dual_stationarity_relative":stationarity_err},
        "limitations":list(LIMITATIONS)}


class SolveCache:
    """Exact, bounded-lifetime reuse within ONE explicit Calculate operation.

    No rounding of supplies/actions, cross-project state or persisted results.
    Each caller receives a separate witness so later auditing cannot alter a
    different source row. This class does not change the optimization problem.
    """
    def __init__(self):
        self.values = {}
        self.hits = 0
        self.misses = 0

    def solve(self, s, *, vu_N, tu_Nmm, mu_Nmm=0., nu_tension_N=0.):
        s.validate()
        actions = (vu_N, tu_Nmm, mu_Nmm, nu_tension_N)
        if any(isinstance(v, bool) or not math.isfinite(v) for v in actions):
            raise ValueError('Finite concurrent actions required; unknown is not zero.')
        key = (VERSION, s, *actions, 16)
        if key in self.values:
            self.hits += 1
            return deepcopy(self.values[key])
        self.misses += 1
        result = solve(s, vu_N=vu_N, tu_Nmm=tu_Nmm,
                       mu_Nmm=mu_Nmm, nu_tension_N=nu_tension_N)
        self.values[key] = deepcopy(result)
        return result

    def summary(self):
        return {'hits':self.hits, 'misses':self.misses, 'entries':len(self.values),
                'scope':'Exact supplies/actions; this Calculate only; no input rounding or persistence'}


def calculate(s: Supplies, *, vu_N, tu_Nmm, mu_Nmm, nu_tension_N, held_action_intercepts=False,
              solve_cache=None):
    """All three requested calculations use the SAME physical steel inventory."""
    run = solve_cache.solve if solve_cache is not None else solve
    v = run(s,vu_N=1000.,tu_Nmm=0.)
    t = run(s,vu_N=0.,tu_Nmm=1e6)
    vt = run(s,vu_N=vu_N,tu_Nmm=tu_Nmm,mu_Nmm=mu_Nmm,nu_tension_N=nu_tension_N)
    result = {"version":VERSION,"production_status":"UNVALIDATED — REVIEW", "supplies":asdict(s),
        "model_Vn_kN":v.get("capacity_factor") if v.get("ready") else None,
        "model_Tn_kNm":t.get("capacity_factor") if t.get("ready") else None,
        "model_VT_factor":vt.get("capacity_factor") if vt.get("ready") else None,
        "model_VT_DC":vt.get("utilization"),"V":v,"T":t,"VT":vt,
        "accepted_Vn_kN":None,"accepted_Tn_kNm":None,"accepted_VT_factor":None,
        "capacity_definition":"Nominal pure V2/T intercepts at M=N=0, fixed theta; concurrent nominal V2/T ray holds actual M3/N. No phi design acceptance.",
        "limitations":list(LIMITATIONS)}
    if held_action_intercepts:
        # Diagnostics for ranking individual actions: actual signed M3/N are
        # held fixed. These are not the M=N=0 intercepts displayed as Model Vn/Tn.
        for action, v_unit, t_unit, demand in (("V",1000.,0.,abs(vu_N)/1000.),
                                               ("T",0.,1e6,abs(tu_Nmm)/1e6)):
            witness = run(s,vu_N=v_unit,tu_Nmm=t_unit,mu_Nmm=mu_Nmm,nu_tension_N=nu_tension_N)
            capacity = witness.get("capacity_factor") if witness.get("ready") else None
            result[action+"_fixed_MN"] = witness
            result["model_"+action+"_only_actual_MN_"+("kN" if action=="V" else "kNm")] = capacity
            result["model_"+action+"_only_actual_MN_DC"] = (demand/capacity if capacity is not None and capacity>1e-12
                else (0. if demand<=1e-12 and witness.get("ready") else None))
    return result
