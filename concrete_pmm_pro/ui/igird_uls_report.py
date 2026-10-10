"""Compact member/case review of current stored I-girder ULS results.

No solvers, result writes, input activation or invented engineering values.
The project model and the design-member summary remain owned by Analysis/Loads.
"""
from __future__ import annotations

import hashlib
import math
import re
import pandas as pd

from concrete_pmm_pro.ui.igird_case_review import (
    AUTO_CASE, FRAME_KEYS, case_ranking, component_controls, controlling_result,
    filter_case, ratio_text, summary_record,
)

CHECK_LABELS = {'Flexure': 'Flexure — Final Composite', 'Shear': 'Shear',
                'Torsion': 'Torsion', 'Shear + Torsion': 'Shear + Torsion'}


def report_member_inputs(state):
    from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
    from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY
    if state.get('section_preset_key') != 'parametric_i_girder':
        return {}
    rows = mr.member_inputs(state)
    active = state.get(ACTIVE_KEY)
    active_rows = ap._active_beam_uls_demand_dataframe_from_session(state)
    if active in rows:
        # An edit in the design table is authoritative even before bank save.
        rows[active] = active_rows
    elif not rows and not active_rows.empty:
        rows[active or 'Design member'] = active_rows
    return rows


def current_check_packages(state, check_name, *, member_rows=None):
    """Only input/version-matched production packages can supply report charts."""
    from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
    from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY
    if check_name not in FRAME_KEYS or state.get('section_preset_key') != 'parametric_i_girder':
        return {}
    route = ap._beam_uls_strength_route_from_state(state, is_bridge=True, is_building=False)
    rows_by_member = report_member_inputs(state) if member_rows is None else member_rows
    active = state.get(ACTIVE_KEY) or 'Design member'
    owner = CHECK_LABELS[check_name]
    expected_version = ap._beam_uls_expected_result_version(state, owner)
    cache = state.get(mr.CACHE_KEY, {})
    packages = {}
    for member, rows in rows_by_member.items():
        if rows.empty:
            continue
        fingerprint = mr.result_hash(state, rows, check_name=check_name, route=route)
        result = mr.current_result(cache, member, check_name, fingerprint)
        if result is None and member == active:
            result = ap._beam_uls_current_cached_result(state, owner, fingerprint)
        if not isinstance(result, dict) or result.get('error'):
            continue
        frame = result.get(FRAME_KEYS[check_name])
        # Collection hashes include result versions. Manual cache entries also
        # have an explicit version checked by the accepted cache accessor.
        if (result.get('result_version') not in (None, expected_version)
                or not isinstance(frame, pd.DataFrame) or frame.empty
                or 'Case' not in frame or frame['Case'].dropna().empty):
            continue
        if check_name == 'Torsion':
            diagram = result.get('torsion_diagram_capacity_df')
            if not isinstance(diagram, pd.DataFrame) or diagram.empty:
                continue
        packages[member] = {'rows': rows, 'result': result}
    return packages


def _short(value, limit=55):
    value = str(value)
    return value if len(value) <= limit else value[:limit-1] + '…'


def make_package_figure(state, package, *, member, check_name, code_label, case=None,
                        chart_view='Selected case — demand / capacity'):
    """Render one original girder/case through the accepted Analysis builders."""
    from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
    from concrete_pmm_pro.ui import igird_vt_workspace as vt
    from concrete_pmm_pro.visualization.igird_uls_chart_display import add_igird_report_note
    frame = package['result'][FRAME_KEYS[check_name]]
    member_control = controlling_result(frame, check_name)
    if case is None:
        case = (member_control['row'] or {}).get('Case')
    cases = frame['Case'].dropna().astype(str).drop_duplicates().tolist()
    if case is None or str(case) not in cases:
        return None
    case = str(case)
    checked = filter_case(frame, case)
    rows = filter_case(package['rows'], case, column='Case Name')
    result = package['result']
    span = ap._beam_uls_span_length_from_state(state, is_building=False)
    if check_name == 'Flexure':
        fig = mr.make_member_flexure_figure(state, rows, checked, member=member,
            code_label=code_label, case_name=case, source_context_df=package['rows'])
        meaning = 'Blue: signed Mux. Red: stored sectional φMn. Composite acceptance also needs effective-width, development and interface-shear gates.'
    elif check_name == 'Shear':
        fig = vt.make_shear_case_figure(package['rows'], frame, case=case,
            code_label=code_label, span_m=span, member_name=member,
            diagram=result.get('shear_diagram_capacity_df'),
            boundary=result.get('shear_boundary_capacity_df'),
            critical=result.get('shear_critical_section_df'))
        meaning = 'Blue: signed Vu. Red: ±φVn from stored station calculations. Strength, detailing and source gates retain their original decisions.'
    elif check_name == 'Torsion':
        if chart_view == 'Overview — utilization':
            from concrete_pmm_pro.ui.igird_torsion_utilization import make_torsion_utilization_figure
            fig = make_torsion_utilization_figure(rows, checked,
                diagram=filter_case(result.get('torsion_diagram_capacity_df'), case),
                code_label=code_label, span_m=span, source_context_df=package['rows'],
                member_name=member, case=case)
            meaning = 'Blue: stored |Tu|/φTn, including qualified below-threshold / zero-Tu stations. Open markers: original maximum design/check D/C; gates remain unchanged.'
        else:
            fig = vt.make_torsion_case_figure(package['rows'], frame, case=case,
                code_label=code_label, span_m=span, member_name=member,
                diagram=result.get('torsion_diagram_capacity_df'),
                boundary=result.get('torsion_boundary_capacity_df'))
            meaning = 'Blue: signed Tu. Red: stored ±φTn, including qualified below-threshold / zero-Tu stations. Diagram resistance is not overall acceptance.'
            if not any(t.name == '±φTn' and any(math.isfinite(float(v)) for v in t.y)
                       for t in fig.data):
                meaning = 'Blue: signed Tu. Purple: stored 0.25φTcr investigation threshold; φTn is unavailable. This is not torsion strength acceptance.'
    else:
        fig = vt.make_overview_figure(rows, checked, check_name=check_name,
            code_label=code_label, span_m=span)
        fig = mr.titled_figure(fig, member, case_name=case)
        meaning = 'Blue: maximum available original V+T component D/C. Red: limit 1.0. ○/× mark omitted ratios, not D/C=0; partial checks remain incomplete.'
    selected_control = controlling_result(checked, check_name)
    location = (selected_control['row'] or {}).get('Governing x', '—')
    meta = dict(fig.layout.meta or {})
    unavailable = (len(meta.get('unavailable_capacity', [])) if check_name != 'Shear + Torsion'
                   else sum(r['classification'] == 'UNAVAILABLE' for r in meta.get('overview_gap_stations', [])))
    # One marker and three shared footer lines remain readable in the standard
    # export. Full original names/rows are retained in metadata and the audit.
    for trace in fig.data:
        if str(trace.name).startswith(('Gov.', 'Governing')):
            trace.mode = 'markers'
            trace.text = None
            trace.showlegend = False
    fig.layout.annotations = tuple(a for a in fig.layout.annotations if a.name != 'igird_report_note')
    global_case = (member_control['row'] or {}).get('Case', 'Unavailable')
    add_igird_report_note(fig, [meaning,
        f"Selected case control ({selected_control['basis']}): {ratio_text(selected_control['ratio'])} @ {location}; {selected_control['failed_rows']} FAIL, {selected_control['review_rows']} REVIEW; ×: {unavailable} unavailable stations.",
        f"All cases: {member_control['failed_rows']} FAIL, {member_control['review_rows']} REVIEW; control: {_short(global_case, 45)} [{member_control['basis']} {ratio_text(member_control['ratio'])}]. Numerical control does not clear gates."])
    fig.update_xaxes(range=[0., span])
    fig.update_layout(meta={**dict(fig.layout.meta or {}), 'igird_report_check': check_name,
        'igird_report_member': member, 'igird_report_case': case,
        'igird_report_view': chart_view,
        'igird_report_selected_control': summary_record(selected_control),
        'igird_report_member_control': summary_record(member_control)})
    return fig


def make_current_report_figure(state, *, check_name, code_label, member=None):
    packages = current_check_packages(state, check_name)
    if not packages or (member is not None and member not in packages):
        return None
    member = member if member is not None else next(iter(packages))
    return make_package_figure(state, packages[member], member=member,
        check_name=check_name, code_label=code_label)


def render_uls_report_charts(state, *, code_label):
    import streamlit as st
    from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY
    from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
    from concrete_pmm_pro.ui import igird_maxmin_charts as mm
    from concrete_pmm_pro.ui.result_table_display import result_table_for_display
    if state.get('section_preset_key') != 'parametric_i_girder':
        return
    with st.expander('I-girder ULS report charts — stored results', expanded=False):
        label = st.selectbox('ULS check for report chart', list(CHECK_LABELS.values()),
                             key='igird_uls_report_check')
        check = next(k for k, v in CHECK_LABELS.items() if v == label)
        rows_by_member = report_member_inputs(state)
        packages = current_check_packages(state, check, member_rows=rows_by_member)
        pending = [n for n in rows_by_member if n not in packages]
        if pending:
            st.warning('No current report result for: ' + '; '.join(pending) +
                       '. Calculate ' + label + ' in Analysis for the current inputs.')
        if not packages:
            st.info('No current I-girder chart is available for this check.')
            return
        token = hashlib.sha256(check.encode()).hexdigest()[:12]
        member_key = 'igird_uls_report_member_' + token
        names = list(packages)
        if state.get(member_key) not in names:
            state[member_key] = state.get(ACTIVE_KEY) if state.get(ACTIVE_KEY) in names else names[0]
        member = st.selectbox('Girder for report chart', names, key=member_key)
        package = packages[member]
        frame = package['result'][FRAME_KEYS[check]]
        control = controlling_result(frame, check)
        controlling_case = str((control['row'] or {}).get('Case', ''))
        cases = frame['Case'].dropna().astype(str).drop_duplicates().tolist()
        case_key = 'igird_uls_report_case_' + hashlib.sha256((check+'\0'+member).encode()).hexdigest()[:16]
        families, case_choices = mm.review_choices(package['rows'], cases)
        options = [AUTO_CASE, *case_choices]
        if state.get(case_key) not in options:
            old_family = mm.family_for_case(families, state.get(case_key))
            state[case_key] = old_family.option if old_family else AUTO_CASE
        choice = st.selectbox('Load case for report chart', options, key=case_key,
                             format_func=lambda value: mm.choice_label(value, families))
        selected_family = next((f for f in families if f.option == choice), None)
        case = (controlling_case if choice == AUTO_CASE else
                (mm.anchor_case(selected_family, frame, check) if selected_family else choice))
        if case not in cases:
            case = cases[0]
        st.caption(f"Controlling stored load case: {controlling_case or 'Unavailable'} · {control['component']} · {control['basis']} {ratio_text(control['ratio'])} @ {(control['row'] or {}).get('Governing x', '—')}. Displayed: {case}.")
        if len(control['tied_cases']) > 1:
            st.info('Equal controlling ratios: ' + '; '.join(control['tied_cases']))
        if control['failed_rows'] or control['review_rows']:
            st.warning(f"All cases for {member}: {control['failed_rows']} failed row(s), {control['review_rows']} row(s) requiring review. Selecting another case does not clear these member-wide gates.")
        st.caption('Chart selectors review stored results. Result Summary and report-readiness cards follow the design member selected in Loads. Calculate all uses the current shared section/deck/reinforcement model for every girder; different member details require separate project models.')
        chart_view = 'Selected case — demand / capacity'
        family = mm.family_for_case(families, case)
        paired = False
        if family:
            chart_view = mm.chart_view(family, check_name=check,
                                       key_prefix='report_'+case_key, state=state)
            paired = chart_view != mm.SOURCE_VIEW
            if not paired:
                source_key = 'igird_uls_report_source_'+case_key
                if state.get(source_key) not in family.cases:
                    state[source_key] = case
                case = st.selectbox('Source vector for report chart', family.cases, key=source_key)
        elif check == 'Torsion':
            chart_view = st.radio('Torsion report chart view',
                ['Selected case — demand / capacity', 'Overview — utilization'],
                horizontal=True, key='igird_uls_report_torsion_view')
        if paired:
            figures = mm.make_bound_figures(state, package, family=family, member=member,
                check_name=check, code_label=code_label, view=chart_view)
            mm.render_bound_figures(figures, family=family, key_prefix='report_'+case_key)
            st.caption('Displayed LC: '+str(family.source['case'])+' · separate Max and Min, all occurrence sets.')
        else:
            fig = make_package_figure(state, package, member=member, check_name=check,
                                      code_label=code_label, case=case, chart_view=chart_view)
            ap._render_beam_uls_browser_plotly_figure(fig, interactive=True)
            figures = {'':fig}
        st.caption('The PNG includes girder, case, units, selected-case control and all-case member gates. Missing resistance/ratios retain their stored gaps and status markers; connecting lines are visual interpolation.')
        with st.expander('Report chart — load-case ranking / source audit', expanded=False):
            st.dataframe(result_table_for_display(case_ranking(frame, check)), hide_index=True, use_container_width=True)
            st.dataframe(result_table_for_display(component_controls(frame, check)), hide_index=True, use_container_width=True)
            checked = mm.select_cases(frame, family.cases) if paired else filter_case(frame, case)
            st.dataframe(result_table_for_display(checked), hide_index=True, use_container_width=True)
            name = (mm.export_name(check, member, family) if paired else
                    re.sub(r'[^A-Za-z0-9_-]+', '_', check+'_'+member+'_'+case).strip('_'))
            st.download_button('Download selected stored check rows (CSV)',
                data=checked.to_csv(index=False).encode('utf-8-sig'),
                file_name=name+'.csv', mime='text/csv', on_click='ignore',
                key='igird_uls_report_csv_'+case_key)
        if check == 'Shear + Torsion' and not paired:
            from concrete_pmm_pro.ui.igird_overview_gaps import render_gap_audit
            render_gap_audit(fig, check_name=check, key_prefix='report_'+case_key)
        if check == 'Torsion' and chart_view == 'Overview — utilization' and not paired:
            from concrete_pmm_pro.ui.igird_torsion_utilization import render_utilization_audit
            render_utilization_audit(fig, key_prefix='report_'+case_key)
        if st.button('Create report chart PNG', key='igird_uls_report_prepare'):
            with st.spinner('Creating report chart image…'):
                images = {step:figure.to_image(format='png', width=1440, height=560, scale=2)
                          for step,figure in figures.items() if figure is not None}
            for step,image in images.items():
                name = (mm.export_name(check, member, family, step) if paired else
                        re.sub(r'[^A-Za-z0-9_-]+', '_', check+'_'+member+'_'+case).strip('_'))
                st.download_button('Download '+(step+' ' if step else '')+'report chart PNG', data=image,
                    file_name=name+'.png', mime='image/png', on_click='ignore',
                    key='igird_uls_report_download'+('_'+step if step else ''))
