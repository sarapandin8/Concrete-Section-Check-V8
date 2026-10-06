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
from concrete_pmm_pro.ui.result_table_display import result_table_for_display
from concrete_pmm_pro.ui.igird_case_review import (
    FRAME_KEYS, AUTO_CASE, ALL_CASES, controlling_result, summary_record,
    filter_case, ratio_text, case_ranking, component_controls,
)

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


def titled_figure(fig, member, *, case_name=None):
    old = str(fig.layout.title.text or '')
    case_line = ''
    if case_name:
        short = case_name if len(case_name) <= 110 else case_name[:107] + '…'
        case_line = f'<sup>Load case: {escape(short)}</sup><br>'
        fig.update_layout(meta={**dict(fig.layout.meta or {}), 'review_case': case_name},
                          margin={'t': max(int(fig.layout.margin.t or 0), 122)})
    fig.update_layout(title={'text': f'Girder: {escape(member)}<br>{case_line}{old}'})
    return fig


def make_member_flexure_figure(state, rows, frame, *, member, code_label, case_name=None, source_context_df=None):
    from concrete_pmm_pro.ui import analysis_page as ap
    span = ap._beam_uls_span_length_from_state(state, is_building=False)
    fig = ap._make_beam_uls_flexure_preview_figure(rows,frame,
        code_label=code_label+' · Final Composite',member_length_m=span,
        source_context_df=source_context_df)
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
    return titled_figure(fig,member,case_name=case_name)


def render_collection(*, check_name, route, code_label):
    """Return True when the collection view owns the current workspace."""
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.ui import igird_vt_workspace as vt
    save_active(st.session_state)
    rows_by_member = member_inputs(st.session_state)
    if not rows_by_member:
        return False
    view = st.radio('Girder results view', ['All imported girders — separate charts',
        'Choose girder / load case — stored results', 'Selected girder — detailed checks'],
        horizontal=True, key='igird_member_results_view')
    if view == 'Selected girder — detailed checks':
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
    results = {}
    controls = {}
    summaries = []
    for n in names:
        # Also reuse an already-calculated selected-member result from the
        # detailed view without rerunning a solver merely to draw a chart.
        result = current_result(cache, n, check_name, fingerprints[n])
        if result is None and n == st.session_state.get(ACTIVE_KEY):
            owner = 'Flexure — Final Composite' if check_name == 'Flexure' else check_name
            result = ap._beam_uls_current_cached_result(st.session_state, owner, fingerprints[n])
        results[n] = result
        if result is not None and not result.get('error'):
            controls[n] = controlling_result(result.get(FRAME_KEYS[check_name]),check_name)
            summaries.append({'Girder':n,'Result state':'CURRENT',**summary_record(controls[n])})
        else:
            summaries.append({'Girder':n,'Result state':'ERROR' if result is not None else
                ('STALE' if cache.get(n,{}).get(check_name) else 'NOT CALCULATED')})
    st.markdown('##### Controlling load cases — '+check_name)
    st.dataframe(result_table_for_display(pd.DataFrame(summaries)),hide_index=True,use_container_width=True)
    st.caption('Numerical control is the largest available stored D/C across the relevant strength and detailing checks. It can differ between checks. Ties are retained; the first tied case is shown automatically. Unresolved source/development gates remain separate from numerical control.')
    shown_names = names
    if view == 'Choose girder / load case — stored results':
        key = 'igird_review_member_'+check_name
        if st.session_state.get(key) not in names:
            active = st.session_state.get(ACTIVE_KEY)
            st.session_state[key] = active if active in names else names[0]
        shown_names = [st.selectbox('Girder to review',names,key=key)]
        st.caption('This selection changes the displayed results. The design member selected in Loads and the Result Summary / Report remain tied to that member.')
    for n in shown_names:
        result = results[n]
        st.markdown('##### Girder: '+escape(n))
        if result is None:
            stale = bool(cache.get(n, {}).get(check_name))
            st.warning(('STALE — inputs changed. ' if stale else 'NOT CALCULATED. ')+f'Calculate {check_name} for this collection before viewing {n}.')
            continue
        if result.get('error'):
            st.error(str(result['error']))
            for message in result.get('messages', []):st.caption(str(message))
            continue
        all_rows = rows_by_member[n]
        full_frame = result.get(FRAME_KEYS[check_name])
        if full_frame is None or full_frame.empty:
            st.warning('No calculated stations are available for this girder.')
            continue
        control = controls[n]
        source = control['row'] or {}
        controlling_case = str(source.get('Case',''))
        st.caption(f"Controlling case: {controlling_case or 'Unavailable'} · {control['component']} · {control['basis']} {ratio_text(control['ratio'])} · x={source.get('Governing x','-')} · stored status {source.get('Status','REVIEW')}")
        if len(control['tied_cases']) > 1:
            st.info('Equal controlling ratios: '+'; '.join(control['tied_cases']))
        if control['failed_rows'] or control['review_rows']:
            st.warning(f"All cases for {n}: {control['failed_rows']} failed row(s), {control['review_rows']} row(s) requiring review. Viewing a passing case does not clear these member-wide gates.")
        if control['basis'] == 'INVESTIGATION ONLY':
            st.info('Torsion control is |Tu|/(0.25φTcr) because strength D/C is unavailable. This is an investigation threshold, not a φTn strength acceptance.')
        elif control['basis'] == 'NO NUMERIC D/C':
            st.info('No numerical governing D/C is available. Automatic selection shows a stored source-review row; complete the required inputs before strength acceptance.')
        cases = all_rows['Case Name'].dropna().astype(str).drop_duplicates().tolist()
        cases += [c for c in full_frame['Case'].dropna().astype(str).drop_duplicates() if c not in cases]
        token = hashlib.sha256(n.encode()).hexdigest()[:16]
        case_key = 'igird_review_case_'+check_name+'_'+token
        options = [AUTO_CASE,ALL_CASES,*cases]
        if st.session_state.get(case_key) not in options:
            st.session_state[case_key] = AUTO_CASE
        choice = st.selectbox('Load case to review — '+n,options,key=case_key)
        case = (controlling_case if controlling_case in cases else (cases[0] if cases else None)) if choice == AUTO_CASE else (None if choice == ALL_CASES else choice)
        st.caption('Displayed load case: '+(case if case is not None else 'All load cases')+' · '+n)
        with st.expander('Load-case ranking / controlling components — '+n,expanded=False):
            st.dataframe(result_table_for_display(case_ranking(full_frame,check_name)),hide_index=True,use_container_width=True)
            st.dataframe(result_table_for_display(component_controls(full_frame,check_name)),hide_index=True,use_container_width=True)
        rows = filter_case(all_rows,case,column='Case Name')
        selected = {key: filter_case(value,case) if isinstance(value,pd.DataFrame) else value
                    for key,value in result.items()}
        label = code_label+' · '+n
        if check_name == 'Flexure':
            frame = selected.get('flexure_preview_df')
            if frame is None or frame.empty:
                st.warning('No calculated flexure stations are available for this girder.')
                continue
            gov = ap._beam_uls_governing_flexure_preview_row(frame)
            if gov:
                st.caption(f"Section flexure: {gov.get('Status','REVIEW')} · D/C {gov.get('Utilization','-')} · {gov.get('Case','-')} @ {gov.get('Governing x','-')}")
            st.caption('Final Composite sectional resistance. Overall composite acceptance additionally requires confirmed effective width, developed deck/girder steel, concurrent source actions and current girder–deck interface shear verification for this member.')
            fig = make_member_flexure_figure(st.session_state,rows,frame,member=n,code_label=code_label,
                case_name=case,source_context_df=all_rows)
            ap._render_beam_uls_browser_plotly_figure(fig,interactive=True)
            st.caption('Each demand series belongs only to this girder. C labels identify its case/vector series; full source names remain on hover and in the stored audit. Coincident resistance curves share one legend entry.')
            from concrete_pmm_pro.ui.igird_flexure_development import render_failure_summary, render_trace
            render_failure_summary(frame,stage='Final Composite · '+n)
            render_trace(frame,stage='Final Composite · '+n)
        elif check_name in {'Shear','Torsion'}:
            kind = check_name.lower()
            frame = selected.get(kind+'_check_df')
            gov = ap._beam_uls_shear_decision_summary(frame).get('row') if check_name == 'Shear' else ap._beam_uls_governing_torsion_row(frame)
            if gov:
                st.caption(f"{check_name}: {gov.get('Status','REVIEW')} · {gov.get('Case','-')} @ {gov.get('Governing x','-')}")
                with st.expander('Calculation trace / Equations — '+check_name+' · '+n,expanded=False):
                    trace = ap._beam_uls_shear_calculation_trace_dataframe(gov) if check_name == 'Shear' else ap._beam_uls_torsion_calculation_trace_dataframe(gov)
                    st.dataframe(result_table_for_display(trace),hide_index=True,use_container_width=True)
                with st.expander('Variable definitions / Engineering terms — '+n,expanded=False):
                    definitions = ap._beam_uls_shear_variable_definitions_dataframe() if check_name == 'Shear' else ap._beam_uls_torsion_variable_definitions_dataframe()
                    st.dataframe(result_table_for_display(definitions),hide_index=True,use_container_width=True)
            vt.render_strength_chart(rows,frame,check_name=check_name,code_label=code_label,state=st.session_state,
                boundary=selected.get(kind+'_boundary_capacity_df'),critical=selected.get('shear_critical_section_df'),
                diagram=selected.get(kind+'_diagram_capacity_df'),key_prefix='member_'+token,member_name=n,
                selected_case=case,source_context_df=all_rows)
        else:
            frame = selected.get('combined_vt_df')
            if frame is None or frame.empty:
                st.warning('No calculated combined stations are available for this girder.')
                continue
            from concrete_pmm_pro.ui.igird_combined_vt import render_workspace
            render_workspace(frame,code_label=label,member_name=n,selected_case=case)
        frame_key = {'Flexure':'flexure_preview_df','Shear':'shear_check_df','Torsion':'torsion_check_df','Shear + Torsion':'combined_vt_df'}[check_name]
        with st.expander('Stored check rows / source audit — '+n,expanded=False):
            frame = selected.get(frame_key)
            if frame is not None:st.dataframe(result_table_for_display(frame),hide_index=True,use_container_width=True)
    st.caption('Member results are stored for this session only. Save Project JSON retains the member input collection; calculate again after loading. Result Summary and Report/QA continue to summarize the selected member, not the complete collection.')
    return True
