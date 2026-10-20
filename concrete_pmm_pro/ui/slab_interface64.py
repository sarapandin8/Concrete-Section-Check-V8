"""Read current Final Composite interface results, without running a solver.

The linked status belongs to each imported girder, not all physical bridge
lines. The interface equation is longitudinal flexural interface transfer;
opening/roll/full six-action joint acceptance remains a separate mechanism.
"""
from __future__ import annotations
import math
import pandas as pd
from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY


def linked_results(state):
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.ui import igird_flexure_workspace as flex
    from concrete_pmm_pro.ui import igird_member_results as members
    source=members.member_inputs(state)
    active=state.get(ACTIVE_KEY)
    active_rows=ap._active_beam_uls_demand_dataframe_from_session(state)
    if active in source and not active_rows.empty:
        source[active]=active_rows
    if not source:
        rows=active_rows
        if not rows.empty:
            active=str(active or 'Design girder')
            source={active:rows}
    route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
    settings=ap._igird_interface_shear_settings_from_state(state)
    cache=state.get(flex.CACHE_KEY,{})
    records=[]
    for name,rows in source.items():
        current_hash=ap._igird_interface_shear_hash(state,ap._igird_interface_source_dataframe(rows),settings=settings,strength_route=route)
        saved=cache.get(name,{}) if isinstance(cache,dict) else {}
        own=(saved.get('bundle') or {}).get('interface',{})
        hash_ok=saved.get('version')==flex.VERSION and (saved.get('hashes') or {}).get('interface')==current_hash
        present=bool(saved)
        owner='Flexure member collection'
        if not hash_ok and name==active:
            legacy=ap._beam_uls_manual_cache(state).get(ap._IGIRDER_INTERFACE_SHEAR_CHECK_NAME,{})
            if isinstance(legacy,dict) and legacy:
                present=True
                # Existing stage cache is itself the result payload.
                if legacy.get('input_hash')==current_hash:
                    own=legacy;hash_ok=True;owner='Flexure active design member'
        version_ok=own.get('result_version')==ap._IGIRDER_INTERFACE_SHEAR_RESULT_VERSION
        frame=own.get('interface_shear_df')
        if hash_ok and version_ok and isinstance(frame,pd.DataFrame) and not frame.empty:
            status=ap._igird_interface_overall_status(frame)
            # Do not trust a green cached headline when row values are missing.
            dc=pd.to_numeric(frame.get('Strength D/C',frame.get('D/C',pd.Series(dtype=float))),errors='coerce')
            minimum=pd.to_numeric(frame.get('Minimum Avf D/C',pd.Series(dtype=float)),errors='coerce')
            values=pd.concat((dc,minimum),ignore_index=True)
            max_dc=float(values.max()) if values.notna().any() else float('nan')
            reason='Current stored AASHTO 5.7.4 longitudinal interface result'
            if status=='PASS' and values.gt(1+1e-8).any():
                status='FAIL';reason='Stored numeric strength / minimum reinforcement check exceeds 1.0'
            if status=='PASS' and (len(dc)!=len(frame) or len(minimum)!=len(frame) or
                    not math.isfinite(max_dc) or dc.isna().any() or minimum.isna().any()):
                status='REVIEW';reason='Stored interface rows have incomplete numeric checks'
        else:
            status='STALE' if present else 'NOT CALCULATED'
            max_dc=float('nan')
            reason='Recalculate Flexure for current inputs' if present else 'Calculate Flexure → Final — Composite'
        records.append({'Girder':name,'Interface status':status,'Max D/C':max_dc,
            'Source':owner,'Scope':'This girder only · longitudinal flexural interface transfer','Action':reason})
    if not records:
        records=[{'Girder':'No imported girder demand','Interface status':'NOT CALCULATED','Max D/C':float('nan'),
            'Source':'Flexure → Final — Composite','Scope':'No bridge-wide interface acceptance inferred',
            'Action':'Import Final ULS girder loads, then Calculate Flexure'}]
    table=pd.DataFrame(records)
    statuses=table['Interface status']
    overall='FAIL' if statuses.eq('FAIL').any() else 'PASS' if statuses.eq('PASS').all() else 'REVIEW'
    return {'rows':table,'status':overall,'members':len(source),
        'scope':'Read-only existing longitudinal interface results for the listed members; no spatial mapping to all bridge girders or full opening/roll joint acceptance is inferred.'}
