"""Whole-girder flexural interface shear; separate from torsion resistance.

This is a traceable comparison of the existing AASHTO vertical-shear result
(Vc + Vs from I hoops) with Article 5.7.4 interface transfer. It does not add
the interface resistance to vertical shear, or credit an unverified U return
as a code-qualified vertical stirrup. No solver runs in presentation code.
"""
import math

from .igird_interface_shear import (
    SURFACE_PRESETS, interface_shear_demand_si, interface_shear_resistance_si,
    minimum_interface_reinforcement_si,
)

VERSION = 'IGIRDER.COMPOSITE50.code-interface-reference'


def check(*, vu_kN, bvi_mm, dv_interface_mm, fc_weaker_MPa,
          avf_mm2_per_m, fy_MPa, surface_key, anchor_dimensions_ready,
          anchorage_declared, effective_width_verified, shear_trace):
    """Same source vector, series checks, native SI, Pc=0.

    The numerical reference assumes the entered clean-surface condition and
    measured anchorage. Unresolved drawing/section gates remain explicit.
    The minimum of web and joint is a flexural-shear reference only; it is
    never a full-composite V-T design result or a second steel contribution.
    """
    if surface_key not in SURFACE_PRESETS:
        raise ValueError('Known interface surface condition required.')
    vals = (vu_kN, bvi_mm, dv_interface_mm, fc_weaker_MPa, avf_mm2_per_m, fy_MPa)
    if any(isinstance(v,bool) or not math.isfinite(float(v)) for v in vals) or min(vals[1:]) <= 0:
        raise ValueError('Finite total Vu and positive measured interface inputs required.')
    avf = avf_mm2_per_m if anchor_dimensions_ready else 0.
    demand = interface_shear_demand_si(vu_kN=vu_kN,bvi_mm=bvi_mm,dv_mm=dv_interface_mm)
    resistance = interface_shear_resistance_si(bvi_mm=bvi_mm,fc_weaker_MPa=fc_weaker_MPa,
        avf_provided_mm2_per_m=avf,fy_MPa=fy_MPa,surface_key=surface_key,phi=.90,pc_N_per_m=0.)
    minimum = minimum_interface_reinforcement_si(bvi_mm=bvi_mm,fy_MPa=fy_MPa,
        demand_Vui_N_per_m=demand['Vui_N'],c_MPa=resistance['c_MPa'],mu=resistance['mu'],phi=.90)
    qn = resistance['Vni_N']/1000.  # N/mm == kN/m
    qr = resistance['Vri_N']/1000.
    joint_vertical = qn*dv_interface_mm/1000.
    joint_design = qr*dv_interface_mm/1000.
    def positive(key):
        try: value=float(shear_trace[key])
        except (KeyError,ValueError,TypeError): return None
        return value if math.isfinite(value) and value>0 else None
    web_nominal, web_design = positive('Vn kN'), positive('φVn kN')
    nominal = min(web_nominal,joint_vertical) if web_nominal is not None else None
    design = min(web_design,joint_design) if web_design is not None else None
    min_dc=minimum['Avf_min_required_mm2_per_m']/avf if avf>0 else None
    gates=[]
    if not anchor_dimensions_ready: gates.append('U anchorage dimensions are inadequate or unavailable.')
    if not anchorage_declared: gates.append('Existing connector anchorage declaration remains unresolved.')
    if not effective_width_verified: gates.append('Composite effective width Be remains unverified for strength.')
    if web_nominal is None or web_design is None: gates.append('Existing vertical code-shear source is incomplete.')
    return {'version':VERSION,'scope':'Flexural-shear reference only; excludes coupled torsion and U-return vertical-shear qualification',
        'production_status':'REFERENCE — REVIEW','accepted_Vn_kN':None,
        'Vu_total_kN':abs(vu_kN),'dv_interface_mm':dv_interface_mm,'bvi_mm':bvi_mm,
        'q_total_kN_per_m':demand['Vui_kN_per_m'],'vui_MPa':demand['vui_MPa'],
        'q_nominal_kN_per_m':qn,'q_design_kN_per_m':qr,
        'interface_DC':demand['Vui_kN_per_m']/qr if qr>0 else None,
        'Avf_provided_mm2_per_m':avf_mm2_per_m,'Avf_credited_mm2_per_m':avf,
        'Avf_min_required_mm2_per_m':minimum['Avf_min_required_mm2_per_m'],'Avf_min_DC':min_dc,
        'Vn_web_I_hoops_kN':web_nominal,'phiVn_web_I_hoops_kN':web_design,
        'Vn_interface_equivalent_kN':joint_vertical,'phiVn_interface_equivalent_kN':joint_design,
        'reference_Vn_series_kN':nominal,'reference_phiVn_series_kN':design,
        'reference_DC':abs(vu_kN)/design if design is not None and design>0 else None,
        'reference_governing':'Web Vc + Vs(I)' if web_nominal is not None and web_nominal<=joint_vertical else 'Whole-girder interface',
        'unresolved_gates':gates,'surface_key':surface_key,'resistance':resistance,
        'U_vertical_shear_credit_in_code_reference':False,
        'steel_policy':'I hoops in vertical code shear; U legs in joint Avf; series checks, never sum the two capacities.'}
