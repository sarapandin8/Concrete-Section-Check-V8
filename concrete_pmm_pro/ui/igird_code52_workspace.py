"""Compact code checks from stored results; research is a separate explicit action.

Review selections never activate another design member or calculate resistance.
The optional study uses its own input-bound, runtime-only research cache.
"""
from copy import deepcopy
import hashlib

import pandas as pd
import streamlit as st

from .igird_case_review import (
    AUTO_CASE, ALL_CASES, FRAME_KEYS, case_ranking, component_controls,
    controlling_result, filter_case, ratio_text,
)
from .result_table_display import result_table_for_display

AUTO_MEMBER = 'Automatic — controlling girder'
STUDY_LABEL = 'Case study — Composite model (LP)'
DETAIL_LABEL = 'Calculation details / Equations'
AUDIT_LABEL = 'Load cases / Source audit'


def _render_plot(fig, *, key):
    from . import analysis_page as ap
    token = hashlib.sha256(key.encode()).hexdigest()[:16]
    fig.update_layout(title={'x': .5, 'xanchor': 'center', 'y': .94, 'yanchor': 'top'})
    with st.container(key='code52_plot_'+token):
        ap._render_beam_uls_browser_plotly_figure(fig, interactive=True, key=key)


def study_fingerprint(state, rows, *, member, route):
    from . import analysis_page as ap
    from concrete_pmm_pro.analysis.igird_composite_steel45 import VERSION
    shared = ap._beam_uls_check_input_hash(state, rows,
        strength_route=route, check_name='Shear + Torsion')
    return 'case52:' + hashlib.sha256((member + VERSION + shared).encode()).hexdigest()


def run_study(state, rows, *, member, route):
    """Explicit study action only; publish nothing to production result caches."""
    from . import igird_composite_steel45 as research, igird_shear_section
    fingerprint = study_fingerprint(state, rows, member=member, route=route)
    local = deepcopy({k: v for k, v in dict(state).items() if k not in {
        'igird_member_uls_runtime_results', 'igird_flexure31_runtime_results', research.RUNTIME_KEY}})
    local['beam_uls_loads_table'] = rows.copy(deep=True)
    # Replace any cached active design member with the selected study member.
    local[igird_shear_section.RUNTIME_KEY] = {'active_df': rows.copy(deep=True)}
    try:
        result = research.calculate(local, rows, route=route)
    except (ValueError, TypeError, KeyError, AttributeError, ImportError) as exc:
        result = {'enabled': True, 'rows': [], 'reason': str(exc),
                  'production_status': 'UNVALIDATED — REVIEW'}
    research.detach_review(state, {research.KEY: result}, fingerprint=fingerprint)
    return result


def _study(state, rows, *, member, route, key):
    from . import igird_composite_steel45 as research
    with st.expander(STUDY_LABEL, expanded=False):
        st.caption('Optional U-leg / slab study across all source cases of the selected girder. Run only on request; '
            'results are separate from code checks, Summary and Report.')
        fingerprint = study_fingerprint(state, rows, member=member, route=route)
        result = research.current(state, fingerprint)
        if st.button('Run case study — selected girder', key=key+'_study', type='secondary'):
            with st.spinner('Calculating composite case study: '+member):
                result = run_study(state, rows, member=member, route=route)
        if result is None:
            st.info('No case study for the current inputs. LP does not run automatically.')
        else:
            research.render(result)


def _case_label(value, families):
    from . import igird_maxmin_charts as mm
    family = next((f for f in families if f.option == value), None)
    if family and sum(str(f.source['case']) == str(family.source['case']) for f in families) == 1:
        return str(family.source['case'])+' · Max / Min'
    return mm.choice_label(value, families)


def _cards(control):
    from . import analysis_page as ap
    row = control['row'] or {}
    failed, review = control['failed_rows'], control['review_rows']
    status = ('FAIL' if failed else 'REVIEW' if review or control['basis'] != 'D/C'
              else str(row.get('Status') or 'REVIEW'))
    ap._render_analysis_summary_strip([
        {'title': 'Code check · all load cases', 'value': status,
         'detail': f'{failed} failed · {review} requiring review',
         'status': 'danger' if failed else 'warning' if status != 'PASS' else 'ready', 'strong': True},
        {'title': 'Controlling '+control['basis'], 'value': ratio_text(control['ratio']),
         'detail': control['component'], 'status': 'info'},
        {'title': 'Controlling station', 'value': str(row.get('Governing x') or 'Unavailable'),
         'detail': 'All stored cases for this girder', 'status': 'neutral'},
    ], columns=3)
    if control['basis'] == 'INVESTIGATION ONLY':
        st.info('|Tu|/(0.25φTcr) is an investigation threshold, not a strength D/C against φTn.')
    elif control['basis'] == 'NO NUMERIC D/C':
        st.info('No numerical D/C is available. Review the missing inputs in Calculation details.')


def _plots(state, rows, result, *, member, case, family, check_name, code_label, key):
    from . import analysis_page as ap, igird_maxmin_charts as mm, igird_vt_workspace as vt
    from .igird_member_results import titled_figure
    if family:
        view = mm.UTILIZATION_VIEW if check_name == 'Shear + Torsion' else mm.DEMAND_VIEW
        figures = mm.make_bound_figures(state, {'rows': rows, 'result': result},
            family=family, member=member, check_name=check_name, code_label=code_label, view=view)
        anchor = mm.anchor_case(family, result[FRAME_KEYS[check_name]], check_name)
        default_step = 'Min' if anchor in family.groups['Min'] else 'Max'
        tab_key = key+'_bounds_'+hashlib.sha256(member.encode()).hexdigest()[:12]+'_'+family.token
        for tab, step in zip(st.tabs(['Max', 'Min'], default=default_step, key=tab_key), ('Max', 'Min')):
            with tab:
                fig = figures[step]
                if fig is None:
                    st.warning(step+' unavailable — no source/check rows for this bound. No values are inferred from the other bound.')
                else:
                    _render_plot(fig, key=key+'_'+family.token+'_'+step)
        return
    selected = {k: filter_case(v, case) if isinstance(v, pd.DataFrame) else v for k, v in result.items()}
    frame = selected[FRAME_KEYS[check_name]]
    active = filter_case(rows, case, column='Case Name')
    if frame.empty:
        st.warning('No stored check rows for the selected load case.')
        return
    span = ap._beam_uls_span_length_from_state(state, is_building=False)
    if check_name == 'Shear + Torsion':
        fig = vt.make_overview_figure(active, frame, check_name=check_name, code_label=code_label, span_m=span)
    else:
        kind = check_name.lower()
        kw = dict(code_label=code_label, span_m=span,
            boundary=selected.get(kind+'_boundary_capacity_df'),
            diagram=selected.get(kind+'_diagram_capacity_df'), source_context_df=rows)
        if check_name == 'Shear':
            kw['critical'] = selected.get('shear_critical_section_df')
        if case is None:
            fig = vt.make_strength_all_cases_figure(active, frame, check_name=check_name, **kw)
        elif check_name == 'Shear':
            fig = vt.make_shear_case_figure(active, frame, case=case, **kw)
        else:
            fig = vt.make_torsion_case_figure(active, frame, case=case, **kw)
    fig = titled_figure(fig, member, case_name=case)
    _render_plot(fig, key=key+'_chart')


def render(*, state, rows_by_member, results, controls, summary, check_name, route, code_label):
    """Two review selectors, one visible graph and collapsed supporting evidence."""
    from . import analysis_page as ap, igird_code52 as policy, igird_maxmin_charts as mm
    from . import igird_print50 as printed
    # Preserve readable native Plotly labels on a phone. The local viewport
    # scrolls horizontally instead of squeezing/truncating engineering notes.
    # Screen-only CSS leaves the existing A4 print adapter unchanged.
    st.html('''<style>
      .code52-mobile-chart-hint {display:none}
      @media screen and (max-width:760px) {
        [class*="st-key-code52_plot_"] {overflow-x:auto;max-width:100%}
        [class*="st-key-code52_plot_"] [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]),
        [class*="st-key-code52_plot_"] [data-testid="stPlotlyChart"] {min-width:780px}
        .code52-mobile-chart-hint {display:block;color:#64748b;font-size:12px}
      }
    </style><div class="code52-mobile-chart-hint">Scroll the chart horizontally to view the full plot.</div>''')
    names = list(rows_by_member)
    key = 'igird_code52_'+check_name
    member_key = key+'_member'
    options = [AUTO_MEMBER, *names]
    if state.get(member_key) not in options:
        state[member_key] = AUTO_MEMBER
    cols = st.columns([1, 1])
    with cols[0]:
        choice = st.selectbox('Girder to review', options, key=member_key,
            disabled=len(names) == 1)
    member = policy.default_member(names, controls) if choice == AUTO_MEMBER else choice
    rows, result = rows_by_member[member], results.get(member)
    frame = result.get(FRAME_KEYS[check_name]) if result else None
    control = controls.get(member)
    cases = rows['Case Name'].dropna().astype(str).drop_duplicates().tolist()
    if isinstance(frame, pd.DataFrame) and 'Case' in frame:
        cases += [c for c in frame['Case'].dropna().astype(str).drop_duplicates() if c not in cases]
    families, choices = mm.review_choices(rows, cases)
    case_key = key+'_case_'+hashlib.sha256(member.encode()).hexdigest()[:12]
    case_options = [AUTO_CASE, ALL_CASES, *choices]
    if state.get(case_key) not in case_options:
        state[case_key] = AUTO_CASE
    with cols[1]:
        lc = st.selectbox('Load case to review', case_options, key=case_key,
            format_func=lambda value: _case_label(value, families))
    gov_case = str(((control or {}).get('row') or {}).get('Case') or (cases[0] if cases else ''))
    family = (mm.family_for_case(families, gov_case) if lc == AUTO_CASE else
              next((f for f in families if f.option == lc), None))
    case = None if lc == ALL_CASES else gov_case if lc == AUTO_CASE else lc
    display_case = str(family.source['case'])+' · Max / Min' if family else case or 'All load cases'
    st.caption(member+' · '+display_case)
    pending = summary.loc[summary['Result state'] != 'CURRENT'] if not summary.empty else summary
    failed = sum(c['failed_rows'] for c in controls.values())
    review = sum(c['review_rows'] for c in controls.values())
    st.caption(f'All imported girders: {failed} failed rows · {review} requiring review · '
        f'{len(pending)} awaiting calculation. Review selections do not clear all-case gates.')
    if result is None:
        status = str(summary.loc[summary['Girder'].eq(member), 'Result state'].iloc[0])
        st.warning(status+' — Calculate to display graphs for the current inputs.')
    elif result.get('error'):
        st.error(str(result['error']))
    elif not isinstance(frame, pd.DataFrame) or frame.empty:
        st.warning('No calculated stations for this girder.')
    else:
        control = control or controlling_result(frame, check_name)
        _cards(control)
        _plots(state, rows, result, member=member, case=case, family=family,
            check_name=check_name, code_label=code_label, key=key)
    with st.expander(DETAIL_LABEL, expanded=False):
        st.caption('Code basis: composite C/T and dv with the I-girder web. Torsion uses qualified '
            'closed I-hoop Ao/ph; U + slab torsion credit is not added automatically. '
            'Original CSI Tu and all source, development and interface REVIEW gates are retained.')
        if control:
            gov = control['row']
            if check_name == 'Shear':
                trace = ap._beam_uls_shear_calculation_trace_dataframe(gov)
                definitions = ap._beam_uls_shear_variable_definitions_dataframe()
            elif check_name == 'Torsion':
                trace = ap._beam_uls_torsion_calculation_trace_dataframe(gov)
                definitions = ap._beam_uls_torsion_variable_definitions_dataframe()
            else:
                from . import igird_combined_vt as combined
                trace, definitions = combined.calculation_trace(gov), combined.variable_definitions()
            st.caption('Equations — controlling row across all cases for '+member)
            printed.table(result_table_for_display(trace), member=member, part=key+'_trace')
            with st.expander('Variable definitions', expanded=False):
                st.dataframe(result_table_for_display(definitions), hide_index=True, use_container_width=True)
        if check_name in {'Torsion', 'Shear + Torsion'} and st.toggle(
                'Show reinforcement suggestions', value=False, key=key+'_advisor'):
            from . import igird_rebar_advisor as advisor
            packages = advisor.current_packages(state, rows_by_member,
                route=route, selected_results=results, selected_check=check_name)
            advisor.render_advisor(state, rows_by_member, packages, route=route, key_prefix='code52')
    with st.expander(AUDIT_LABEL, expanded=False):
        printed.table(result_table_for_display(summary), member=key, part='overview')
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            st.caption('Load-case ranking — '+member)
            st.dataframe(result_table_for_display(case_ranking(frame, check_name)), hide_index=True, use_container_width=True)
            st.dataframe(result_table_for_display(component_controls(frame, check_name)), hide_index=True, use_container_width=True)
            st.dataframe(result_table_for_display(frame), hide_index=True, use_container_width=True)
        st.dataframe(ap._beam_uls_audit_dataframe(rows), hide_index=True, use_container_width=True)
        st.caption('Review selectors do not change the design member in Loads. Summary / Report use '
            'the selected design member. Project JSON saves inputs; results are runtime-only.')
    _study(state, rows, member=member, route=route, key=key)
