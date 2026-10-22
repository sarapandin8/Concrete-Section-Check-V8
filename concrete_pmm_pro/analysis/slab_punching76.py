"""Automatic input/scope review; never manufacture a punching footprint or PASS.

Read existing committed load areas and the saved CSI load-basis declaration.
Continuous UDL identifies what the analysis represents, not a code exemption
or a substitute for a local wheel/reaction assessment.
"""
from concrete_pmm_pro.analysis.slab_punching64 import normalise

VERSION = 'SLAB.PUNCHAUTO76'
REFERENCE = 'https://docs.csiamerica.com/help-files/safe/Menus/Design/Punching_Check_Overwrites.htm'


def assessment(areas, basis, source_status, *, check_status='NOT CALCULATED'):
    areas = normalise(areas)
    out = {'version': VERSION, 'source': 'Saved project inputs',
        'source_status': source_status, 'area_count': len(areas),
        'load_method': basis['method'], 'local_check_status': check_status if areas else 'NOT CALCULATED',
        'footprint_inferred_from_shell_results': False, 'code_exemption': False,
        'full_deck_acceptance': False, 'reference': REFERENCE}
    if areas:
        out.update(route='saved_areas', title='Saved physical load areas',
            message=f'{len(areas)} saved load area(s) are used automatically. Slab geometry, material and reinforcement levels are read from the project.',
            action='Use Calculate to evaluate these areas; open the area editor only to change them.')
    elif basis['method'] == 'equivalent_udl':
        matched = source_status == 'SOURCE MATCHED'
        out.update(route='continuous_udl' if matched else 'udl_basis_unmatched',
            title='Continuous train UDL' if matched else 'Train UDL basis needs recording',
            track_width_m=basis['track_width_m'], ballast_mm=basis['ballast_mm'],
            message='The recorded analysis uses a continuous train-load strip. It does not define an isolated wheel or reaction footprint; local punching is not resolved by this UDL model.',
            action='Review one-way shear from the imported CSI results. Add a physical area only for a separate isolated load/reaction check.' if matched else
                'Review the existing CSI load basis / Ballast form and Calculate to record it against the current imported data.')
    else:
        out.update(route='footprint_missing', title='Physical footprint not supplied',
            message='The imported shell-force and geometry tables do not identify the physical dimensions of an isolated load or reaction.',
            action='Use the recorded CSI load model for the automatic review. Add an isolated load area only when its actual position and dimensions are known.')
    return out
