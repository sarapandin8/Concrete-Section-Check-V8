"""Compact I-girder stress workspace: one action, one graph, folded evidence."""
import hashlib
import math
import pandas as pd
import streamlit as st

from . import igird_sls53_results as results

AUTO_CASE = 'Automatic — controlling case'


def _number(value):
    n = results.ratio(value)
    return 'Unavailable' if n == -math.inf else '∞' if n == math.inf else f'{n:.3f}'


def _settings():
    from . import analysis_page as ap
    with st.expander('Check settings / Stress limits', expanded=False):
        ap._render_project_design_code_guard(workflow='girder_sls')
        ap._render_girder_sls4d_all_stage_profile_control_matrix()
        st.caption('Edit geometry and concrete strengths in Sections, prestress in Prestress / Losses, '
                   'and stage loads in Loads. These existing inputs are used directly.')


def _member():
    from concrete_pmm_pro.io import girder_sls_import as source
    names = source.members(st.session_state.get(source.BANK_KEY, []))
    if not names:
        return
    key = 'igird_sls53_member'
    member = source.active_member(st.session_state)
    if st.session_state.get(key) != member:
        st.session_state[key] = member
    def change():
        source.activate_member(st.session_state, st.session_state[key])
        from .girder_sls_import import _sync
        _sync()
    st.selectbox('SLS girder', names, key=key, on_change=change, disabled=len(names) == 1)


def _cards(result):
    from . import analysis_page as ap
    rows = result['summary']
    gov = results.controlling(rows) or {}
    status = results.overall_status(rows)
    failed = sum('FAIL' in str(r['Status']) for r in rows)
    review = sum(r['Status'] == 'REVIEW' for r in rows)
    ap._render_analysis_summary_strip([
        {'title': 'SLS stress · all stages / cases', 'value': status,
         'detail': f'{failed} stages exceeded · {review} requiring review',
         'status': 'danger' if failed else 'warning' if review else 'ready', 'strong': True},
        {'title': 'Controlling stress D/C', 'value': _number(gov.get('Utilization')),
         'detail': str(gov.get('Stage', 'Unavailable'))+' · '+str(gov.get('Controls', '')),
         'status': 'info'},
        {'title': 'Controlling location', 'value': 'x = '+_number(gov.get('Station x (m)'))+' m',
         'detail': str(gov.get('Concrete component', 'Precast beam'))+' · '+str(gov.get('Fiber', '')),
         'status': 'neutral'},
    ], columns=3)


def _details(result, case, *, stage, selected):
    from . import analysis_page as ap
    with st.expander('Calculation details / Equations', expanded=False):
        st.caption('All-stage summary covers every calculated case for '+result['member']+'. '
                   'The graph selectors do not change this summary.')
        cols = ['Stage', 'Status', 'Case Name', 'Concrete component', 'Controls', 'Station x (m)',
                'Fiber', 'Actual stress (MPa)', 'Limit stress (MPa)', 'Utilization', 'Cases checked']
        summary = pd.DataFrame(result['summary'])
        st.dataframe(summary[[c for c in cols if c in summary]], hide_index=True, width='stretch')
        st.markdown('**Elastic stress · compression − / tension +**')
        st.latex(r'\sigma(y)=-\frac{N}{A}+\frac{M(y_c-y)}{I}-\frac{P_e}{A}+\frac{P_e e(y_c-y)}{I},\qquad e=y_{ps}-y_c')
        st.caption('N and Pe: compression positive; y measured upward from the section bottom. '
                   'kN → N ×1,000; kN·m → N·mm ×1,000,000. Each term uses its applicable stage section basis.')
        st.latex(r'\sigma_{beam}=\sigma_{locked}+\sigma_{Pe}+\sigma_{increment},\qquad \sigma_{slab}=n\,\sigma_{increment},\quad n=E_{slab}/E_{beam}')
        st.caption('Composite Service: locked-in construction and prestress act on the precast beam; '
                   'subsequent increments use the transformed section. Imported total resultants retain '
                   'the existing source contract; no extra automatic DL/SDL is added.')
        st.dataframe(pd.DataFrame(case['checks']), hide_index=True, width='stretch')
        split = case['split']
        st.dataframe(split if not split.empty else case['raw'], hide_index=True, width='stretch')
        st.caption('Elastic N–Mx stress-limit preview. Crack width, cracked-section response, '
                   'principal tension, deflection and end-zone detailing are separate checks.')
    with st.expander('Load cases / Source audit', expanded=False):
        st.caption('Graph: '+stage+' · '+selected+' · '+result['member']+'. Source signs, stages and case identities are retained.')
        source_cols = ['Station x (m)', 'Case Name', 'Basis', 'N (kN)', 'User Mx (kN-m)',
            'Auto Mx (kN-m)', 'Mx (kN-m)', 'Pe stage (kN)', 'SLS force content',
            'Auto load components', 'Active PS groups', 'Reference review']
        st.dataframe(case['raw'][[c for c in source_cols if c in case['raw']]], hide_index=True, width='stretch')
        st.download_button('Download stress results · CSV',
            data=case['raw'].to_csv(index=False).encode('utf-8-sig'),
            file_name='SLS_stress_results.csv', mime='text/csv', key='igird_sls53_download')


def render():
    from . import analysis_page as ap, igird_print50 as printed
    from concrete_pmm_pro.visualization.igird_sls53 import stress_figure
    printed.install()
    st.markdown(ap._ANALYSIS_DASHBOARD_CSS, unsafe_allow_html=True)
    st.html('''<style>
      .st-key-igird_sls53_workspace .cpmm-analysis-strip{min-height:96px;padding:.65rem .8rem;margin-bottom:.2rem}
      .st-key-igird_sls53_workspace .cpmm-analysis-value{font-size:1.15rem}
      @media print{
        .st-key-igird_sls53_nav,
        .st-key-igird_sls53_workspace [data-testid="stButton"],
        .st-key-igird_sls53_workspace [data-testid="stRadio"],
        .st-key-igird_sls53_workspace [data-testid="stSelectbox"]{display:none!important}
      }
    </style>''')
    st.caption(ap.workflow_project_code_label_from_session(st.session_state)+
               ' · Elastic stress preview · compression − / tension + · MPa. '
               'Calculate once for all stages and cases of the selected SLS girder.')
    _member()
    _settings()
    try:
        results.prepare()
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        results.clear_handoff(st.session_state)
        st.error('SLS inputs unavailable: '+str(exc))
        return
    result = results.current(st.session_state)
    if result is None:
        results.clear_handoff(st.session_state)
    if st.button('Calculate SLS Stress', type='primary', key='igird_sls53_calculate'):
        try:
            with st.spinner('Calculating all SLS stages and load cases…'):
                result = results.calculate()
        except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError) as exc:
            result = None
            results.clear_handoff(st.session_state)
            st.error('SLS calculation unavailable: '+str(exc))
    if result is None:
        st.info('Calculate SLS Stress to display graphs for the current inputs. '
                'Previous results are hidden after an engineering input changes.')
        return
    results.publish(st.session_state, result)
    _cards(result)
    stages = list(result['stages'])
    key = 'igird_sls53_stage'
    if st.session_state.get(key) not in stages:
        requested = st.session_state.get('_igird_sls23_review_stage')
        st.session_state[key] = requested if requested in stages else 'Service stage' if 'Service stage' in stages else stages[0]
    stage = st.radio('Stage to review', stages, key=key, horizontal=True,
        format_func=lambda s: s.replace(' stage', ''))
    stored = result['stages'][stage]
    choices = [AUTO_CASE, *stored['cases']]
    case_key = 'igird_sls53_case_'+stage.replace(' ', '_')
    if st.session_state.get(case_key) not in choices:
        st.session_state[case_key] = AUTO_CASE
    source_rows = ap._beam_sls_load_rows_from_session_state()
    label = lambda c: c if c == AUTO_CASE else ap._sls_import23_case_label(c, source_rows)
    has_components = any(len(c['limits']) > 1 for c in stored['cases'].values())
    controls = st.columns([2, 1]) if has_components else None
    with controls[0] if controls else st.container():
        choice = st.selectbox('Load case to review', choices, key=case_key, format_func=label)
    selected = str(stored['summary']['Case Name']) if choice == AUTO_CASE else choice
    case = stored['cases'][selected]
    components = list(case['limits'])
    component = components[0]
    if len(components) > 1:
        comp_key = 'igird_sls53_component'
        if st.session_state.get(comp_key) not in components:
            st.session_state[comp_key] = stored['summary'].get('Concrete component', components[0])
        with controls[1] if controls else st.container():
            component = st.radio('Concrete component', components, key=comp_key, horizontal=True,
                format_func=lambda c: 'Slab / CIP' if c == 'CIP / topping' else 'I-girder')
    visible_checks = [r for r in case['checks'] if r.get('Concrete component', 'Precast beam') == component]
    gov = results.controlling(visible_checks) or {}
    st.caption(result['member']+' · '+label(selected)+' · '+results.overall_status(visible_checks)+
        ' · stress D/C '+_number(gov.get('Utilization'))+' · '+str(gov.get('Controls', ''))+
        ' at x='+_number(gov.get('Station x (m)'))+' m · '+_number(gov.get('Actual stress (MPa)'))+
        ' / '+_number(gov.get('Limit stress (MPa)'))+' MPa. Overall status covers all calculated cases.')
    fig = stress_figure(case, stage=stage, component=component, span_m=result['span_m'],
        context_label=result['member']+' · '+label(selected))
    st.html('''<style>
      .sls53-chart-hint{display:none}
      @media screen and (max-width:760px){
        [class*="st-key-sls53_plot_"]{overflow-x:auto;max-width:100%}
        [class*="st-key-sls53_plot_"] [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]),
        [class*="st-key-sls53_plot_"] [data-testid="stPlotlyChart"]{min-width:780px}
        .sls53-chart-hint{display:block;color:#64748b;font-size:12px}
      }</style><div class="sls53-chart-hint">Scroll the chart horizontally to view the full span.</div>''')
    with st.container(key=printed.key('sls53', 'chart_scope')):
        with st.container(key='sls53_plot_'+hashlib.sha256(stage.encode()).hexdigest()[:12]):
            st.plotly_chart(fig, width='stretch', key='igird_sls53_chart',
                config={'displaylogo': False, 'scrollZoom': False, 'toImageButtonOptions': {'filename': 'SLS_stress', 'scale': 2}})
    st.caption(result['code_label']+' · '+case['limits'][component]['label'])
    for issue in case['issues']:
        st.warning(issue)
    profile_warning = str(st.session_state.get(ap._girder_sls_stage_profile_warning_key(stage)) or '')
    if profile_warning:
        st.caption(profile_warning)
    _details(result, case, stage=stage, selected=selected)
