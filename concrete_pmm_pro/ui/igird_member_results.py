"""On-demand member calculations and separate, source-scoped ULS charts.

Only the current member is published to the existing summary cache. Collection
results are runtime-only; Project JSON continues to persist input tables only.
"""
from copy import deepcopy
import hashlib
from html import escape
import pandas as pd
import streamlit as st
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY, ACTIVE_KEY, members, save_active

CACHE_KEY = 'igird_member_uls_runtime_results'


def member_inputs(state):
    from concrete_pmm_pro.ui import analysis_page as ap
    bank = pd.DataFrame(state.get(BANK_KEY, []))
    result = {}
    for member in members(bank):
        local = dict(state)
        local['beam_uls_loads_table'] = bank.loc[bank['Girder'].astype(str).eq(member)].copy()
        rows = ap._active_beam_uls_demand_dataframe_from_session(local)
        if not rows.empty:
            result[member] = rows
    return result


def result_hash(state, rows, *, check_name, route):
    from concrete_pmm_pro.ui import analysis_page as ap
    if check_name == 'Flexure':
        return ap._beam_uls_final_composite_flexure_hash(state, rows, strength_route=route)
    return ap._beam_uls_check_input_hash(state, rows, strength_route=route, check_name=check_name)


def calculate_member(state, rows, *, check_name, route):
    """Use the accepted solver independently for one member's actual vectors."""
    from concrete_pmm_pro.ui import analysis_page as ap
    local = deepcopy({k: v for k, v in dict(state).items() if k not in {CACHE_KEY, BANK_KEY}})
    local['beam_uls_loads_table'] = rows.copy(deep=True)
    if check_name != 'Flexure':
        return ap._beam_uls_calculate_selected_check(local, rows, selected_check=check_name, strength_route=route)
    prep, composite, messages = ap._beam_uls_final_composite_preparation(local)
    if composite is None:
        return {'error': 'Final composite section is not ready.', 'messages': list(messages)}
    params = dict(local.get('section_parameters') or {})
    frame, notes = ap._beam_uls_flexure_preview_dataframe(composite, rows,
        strength_route=route, prestress_force_stage='final', full_span_capacity=True,
        use_aashto_solver=True, apply_girder_development=True)
    return {'flexure_preview_df': frame, 'flexure_preview_messages': [*messages, *notes],
        'result_version': ap._IGIRDER_FINAL_COMPOSITE_FLEXURE_RESULT_VERSION,
        'composite_design_fc_MPa': prep.design_fc_MPa, 'deck_fc_MPa': prep.deck_fc_MPa,
        'girder_fc_MPa': prep.girder_fc_MPa, 'Be_mm': prep.effective_width_mm,
        'Tslab_mm': prep.deck_thickness_mm, 'deck_rebar_credit': prep.deck_rebar_credit_enabled,
        'Be_mode': str(params.get('Be_mode') or 'Manual'),
        'Be_strength_verified': bool(params.get('Be_strength_verified',False)),
        'negative_mux_rows_excluded': 0,
        'negative_mux_rows_screened': int(pd.to_numeric(rows['Mux'],errors='coerce').lt(-ap._BEAM_ULS_DEMAND_TOL).sum())}


def current_result(cache, member, check_name, fingerprint):
    entry = cache.get(member, {}).get(check_name, {})
    return entry.get('result') if entry.get('input_hash') == fingerprint else None


def titled_figure(fig, member):
    old = str(fig.layout.title.text or '')
    fig.update_layout(title={'text': f'Girder: {escape(member)}<br>{old}'})
    return fig


def make_member_flexure_figure(state, rows, frame, *, member, code_label):
    from concrete_pmm_pro.ui import analysis_page as ap
    span = ap._beam_uls_span_length_from_state(state, is_building=False)
    fig = ap._make_beam_uls_flexure_preview_figure(rows,frame,
        code_label=code_label+' · Final Composite',member_length_m=span)
    # Generic app-column cases can share a long member-name prefix. Number
    # those series locally so shortening does not produce identical labels.
    labels = [str(t.name).split('—',1)[-1].strip() for t in fig.data if str(t.name).startswith('Demand Mux')]
    fig = ap._polish_igird_uls_flexure_legend(fig)
    number = 0
    mapping = {}
    for trace in fig.data:
        if str(trace.name).startswith('Demand Mux'):
            number += 1
            trace.name = f'Mux C{number}'
            mapping[trace.name] = labels[number-1] if number <= len(labels) else ''
    if mapping:
        fig.update_layout(meta={**dict(fig.layout.meta or {}), 'member_case_legend':mapping})
    return titled_figure(fig,member)


def render_collection(*, check_name, route, code_label):
    """Return True when the collection view owns the current workspace."""
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.ui import igird_vt_workspace as vt
    save_active(st.session_state)
    rows_by_member = member_inputs(st.session_state)
    if not rows_by_member:
        return False
    view = st.radio('Girder results view', ['All imported girders — separate charts', 'Selected girder — detailed checks'],
        horizontal=True, key='igird_member_results_view')
    if view != 'All imported girders — separate charts':
        return False
    st.markdown(f'#### {check_name} — separate results for each girder')
    st.info('Each girder is calculated separately with all its active ULS cases. This command applies the current section, deck, reinforcement, prestress and support settings to every listed girder. If those details differ, use separate project models before accepting the results.')
    names = list(rows_by_member)
    st.dataframe(pd.DataFrame([{'Girder': n, 'Active rows': len(rows_by_member[n]),
        'Vector series': rows_by_member[n]['Case Name'].nunique()} for n in names]),hide_index=True,use_container_width=True)
    fingerprints = {n: result_hash(st.session_state, rows_by_member[n], check_name=check_name, route=route) for n in names}
    cache = dict(st.session_state.get(CACHE_KEY, {}))
    if st.button(f'Calculate {check_name} — all {len(names)} girders (current model)', type='primary',
            key='igird_member_calculate_'+check_name):
        for n in names:
            with st.spinner(f'Calculating {check_name}: {n}'):
                result = calculate_member(st.session_state, rows_by_member[n], check_name=check_name, route=route)
            member_cache = dict(cache.get(n, {}))
            member_cache[check_name] = {'input_hash': fingerprints[n], 'result': result}
            cache[n] = member_cache
            if n == st.session_state.get(ACTIVE_KEY) and 'error' not in result:
                owner = 'Flexure — Final Composite' if check_name == 'Flexure' else check_name
                ap._beam_uls_store_manual_result(st.session_state, owner, input_hash=fingerprints[n], result=result)
        st.session_state[CACHE_KEY] = cache
    for n in names:
        # Also reuse an already-calculated selected-member result from the
        # detailed view without rerunning a solver merely to draw a chart.
        result = current_result(cache, n, check_name, fingerprints[n])
        if result is None and n == st.session_state.get(ACTIVE_KEY):
            owner = 'Flexure — Final Composite' if check_name == 'Flexure' else check_name
            result = ap._beam_uls_current_cached_result(st.session_state, owner, fingerprints[n])
        st.markdown('##### Girder: '+escape(n))
        if result is None:
            stale = bool(cache.get(n, {}).get(check_name))
            st.warning(('STALE — inputs changed. ' if stale else 'NOT CALCULATED. ')+f'Calculate {check_name} for this collection before viewing {n}.')
            continue
        if result.get('error'):
            st.error(str(result['error']))
            for message in result.get('messages', []):st.caption(str(message))
            continue
        rows = rows_by_member[n]
        label = code_label+' · '+n
        token = hashlib.sha256(n.encode()).hexdigest()[:16]
        if check_name == 'Flexure':
            frame = result.get('flexure_preview_df')
            if frame is None or frame.empty:
                st.warning('No calculated flexure stations are available for this girder.')
                continue
            gov = ap._beam_uls_governing_flexure_preview_row(frame)
            if gov:
                st.caption(f"Section flexure: {gov.get('Status','REVIEW')} · D/C {gov.get('Utilization','-')} · {gov.get('Case','-')} @ {gov.get('Governing x','-')}")
            st.caption('Final Composite sectional resistance. Overall composite acceptance additionally requires confirmed effective width, developed deck/girder steel, concurrent source actions and current girder–deck interface shear verification for this member.')
            fig = make_member_flexure_figure(st.session_state,rows,frame,member=n,code_label=code_label)
            ap._render_beam_uls_browser_plotly_figure(fig,interactive=True)
            st.caption('Each demand series belongs only to this girder. C labels identify its case/vector series; full source names remain on hover and in the stored audit. Coincident resistance curves share one legend entry.')
            from concrete_pmm_pro.ui.igird_flexure_development import render_failure_summary, render_trace
            render_failure_summary(frame,stage='Final Composite · '+n)
            render_trace(frame,stage='Final Composite · '+n)
        elif check_name in {'Shear','Torsion'}:
            kind = check_name.lower()
            frame = result.get(kind+'_check_df')
            gov = ap._beam_uls_shear_decision_summary(frame).get('row') if check_name == 'Shear' else ap._beam_uls_governing_torsion_row(frame)
            if gov:
                st.caption(f"{check_name}: {gov.get('Status','REVIEW')} · {gov.get('Case','-')} @ {gov.get('Governing x','-')}")
                with st.expander('Calculation trace / Equations — '+check_name+' · '+n,expanded=False):
                    trace = ap._beam_uls_shear_calculation_trace_dataframe(gov) if check_name == 'Shear' else ap._beam_uls_torsion_calculation_trace_dataframe(gov)
                    st.dataframe(trace,hide_index=True,use_container_width=True)
                with st.expander('Variable definitions / Engineering terms — '+n,expanded=False):
                    definitions = ap._beam_uls_shear_variable_definitions_dataframe() if check_name == 'Shear' else ap._beam_uls_torsion_variable_definitions_dataframe()
                    st.dataframe(definitions,hide_index=True,use_container_width=True)
            vt.render_strength_chart(rows,frame,check_name=check_name,code_label=code_label,state=st.session_state,
                boundary=result.get(kind+'_boundary_capacity_df'),critical=result.get('shear_critical_section_df'),
                diagram=result.get(kind+'_diagram_capacity_df'),key_prefix='member_'+token,member_name=n)
        else:
            frame = result.get('combined_vt_df')
            if frame is None or frame.empty:
                st.warning('No calculated combined stations are available for this girder.')
                continue
            from concrete_pmm_pro.ui.igird_combined_vt import render_workspace
            render_workspace(frame,code_label=label,member_name=n)
        frame_key = {'Flexure':'flexure_preview_df','Shear':'shear_check_df','Torsion':'torsion_check_df','Shear + Torsion':'combined_vt_df'}[check_name]
        with st.expander('Stored check rows / source audit — '+n,expanded=False):
            frame = result.get(frame_key)
            if frame is not None:st.dataframe(frame,hide_index=True,use_container_width=True)
    st.caption('Member results are stored for this session only. Save Project JSON retains the member input collection; calculate again after loading. Result Summary and Report/QA continue to summarize the selected member, not the complete collection.')
    return True
