"""Read-only currency of the four bridge Analysis subpages.

Current means calculated for the present inputs, never design acceptance.
Only existing source/hash helpers are called; resistance solvers are excluded.
"""
import pandas as pd

ULS_FRAMES = {
    'Flexure — Construction': 'flexure_preview_df',
    'Flexure — Final Composite': 'flexure_preview_df',
    'Interface Shear — Final Composite': 'interface_shear_df',
    'Shear': 'shear_check_df', 'Torsion': 'torsion_check_df',
    'Shear + Torsion': 'combined_vt_df',
}


def current_uls_cache(state):
    """Use the same current-input contract as each I-girder Analysis check."""
    raw = state.get('_beam_girder_uls_manual_calculation_cache') or {}
    if not isinstance(raw, dict):
        return {}
    if state.get('section_preset_key') != 'parametric_i_girder':
        return raw
    if not raw:
        return {}
    from concrete_pmm_pro.ui import analysis_page as ap
    try:
        active = ap._active_beam_uls_demand_dataframe_from_session(state)
        route = ap._beam_uls_strength_route_from_state(state, is_bridge=True, is_building=False)
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
        return {}
    filtered = {}
    for name, entry in raw.items():
        if name not in ULS_FRAMES or not isinstance(entry, dict) or not entry.get('input_hash'):
            continue
        expected = ap._beam_uls_expected_result_version(state, name)
        if name == 'Interface Shear — Final Composite':
            expected = ap._IGIRDER_INTERFACE_SHEAR_RESULT_VERSION
        if expected and entry.get('result_version') != expected:
            continue
        try:
            if name == 'Flexure — Construction':
                _, rows, _ = ap._beam_uls_construction_demand_from_state(state)
                signature = ap._beam_uls_construction_flexure_hash(state, rows, strength_route=route)
            elif name == 'Flexure — Final Composite':
                rows = active.loc[pd.to_numeric(active['Mux'], errors='coerce').notna()].copy()
                signature = ap._beam_uls_final_composite_flexure_hash(state, rows, strength_route=route)
            elif name == 'Interface Shear — Final Composite':
                rows = ap._igird_interface_source_dataframe(active)
                signature = ap._igird_interface_shear_hash(state, rows,
                    settings=ap._igird_interface_shear_settings_from_state(state), strength_route=route)
            else:
                signature = ap._beam_uls_check_input_hash(state, active, strength_route=route, check_name=name)
        except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
            continue
        if str(entry['input_hash']) == signature:
            filtered[name] = entry
    return filtered


def _page(done, total, stored, detail, *, missing=False):
    status = 'CURRENT' if done == total else 'PARTIAL' if done else 'STALE' if stored else 'INPUTS MISSING' if missing else 'NOT CALCULATED'
    return {'status': status, 'done': done, 'total': total, 'detail': detail}


def pages(state):
    from concrete_pmm_pro.ui import igird_sls53_results as stress
    from concrete_pmm_pro.serviceability import girder_deflect70 as deflection
    from concrete_pmm_pro.analysis import slab_review68 as slab
    from concrete_pmm_pro.io.slab_shell_import import current_package
    cache = current_uls_cache(state)
    raw = state.get('_beam_girder_uls_manual_calculation_cache') or {}
    required = list(ULS_FRAMES) if state.get('section_preset_key') == 'parametric_i_girder' else ['Flexure', 'Shear', 'Torsion', 'Shear + Torsion']
    frame_keys = {**ULS_FRAMES, 'Flexure': 'flexure_preview_df'}
    frames = [cache.get(name, {}).get(frame_keys[name]) for name in required]
    done = sum(isinstance(frame, pd.DataFrame) and not frame.empty for frame in frames)
    uls = _page(done, len(required), bool(raw), f'{done}/{len(required)} required stored ULS checks match current inputs')
    stress_result = stress.current(state)
    sls = _page(int(stress_result is not None), 1, stress.RUNTIME_KEY in state,
        'Stored stage stresses for the selected SLS girder' if stress_result else 'Calculate SLS Stress for current inputs')
    deflect_result = deflection.current(state)
    n_stages = 3 if deflect_result and deflect_result['service_available'] else 2 if deflect_result else 0
    disp = _page(n_stages, 3, deflection.RESULT_KEY in state,
        f'{n_stages}/3 stages current; Service uses the imported girder envelope')
    slab_result = slab.current(state)
    deck = _page(int(slab_result is not None), 1, slab.RESULT_KEY in state,
        'Stored Top slab component checks' if slab_result else 'Import the four shell export sets and Calculate Top slab',
        missing=current_package(state) is None)
    return {'ULS Strength': uls, 'SLS / Stress & Cracking': sls,
        'SLS Deflection / Camber': disp, 'Slab Reinforcement': deck}


def aggregate(state):
    modules = pages(state)
    done = sum(row['status'] == 'CURRENT' for row in modules.values())
    partial = any(row['status'] == 'PARTIAL' for row in modules.values())
    stale = any(row['status'] == 'STALE' for row in modules.values())
    label = 'Current' if done == 4 else 'Partial' if done or partial else 'Stale' if stale else 'Not calculated'
    return {'label': f'{label} {done}/4', 'complete': done == 4, 'done': done, 'pages': modules}
