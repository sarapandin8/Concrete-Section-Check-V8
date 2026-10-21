"""One calculation command, four existing mats, one selected engineering plot."""
from __future__ import annotations

import hashlib
import pandas as pd
import streamlit as st

from concrete_pmm_pro.analysis import slab_top65 as engine
from concrete_pmm_pro.analysis import slab_shear64 as accepted, slab_aashto63 as sections, slab_punching64 as punching
from concrete_pmm_pro.analysis import slab_shell56 as inputs
from concrete_pmm_pro.io.slab_shell_import import current_package
from concrete_pmm_pro.ui.commercial import render_page_header, render_metric_cards
from concrete_pmm_pro.ui.slab_aashto63_workspace import number, _trace, _audit, _case_studies
from concrete_pmm_pro.ui.slab_shear64_workspace import _areas, _interface, _punching
from concrete_pmm_pro.ui.slab_interface64 import linked_results
from concrete_pmm_pro.visualization import slab_top65 as plots
from concrete_pmm_pro.visualization.slab_shell56 import ALL_CASES, element_envelope

GROUPS = ['Reinforcement', 'One-way shear', 'Punching shear']


def _load_form(package, error):
    try:
        basis = engine.load_basis(st.session_state)
    except ValueError as exc:
        st.warning(str(exc))
        basis = engine.DEFAULT_BASIS.copy()
    with st.form('slab_shell55_top65_calculation_form'):
        with st.expander('CSI load basis / Ballast', expanded=False):
            method = st.selectbox('Load model used in CSI', list(engine.METHODS),
                index=list(engine.METHODS).index(basis['method']), format_func=engine.METHODS.get,
                key='slab_shell55_top65_method')
            a, b, c = st.columns(3)
            with a:
                ballast = st.number_input('Ballast below sleeper (mm)', min_value=0., value=basis['ballast_mm'], step=25.,
                    key='slab_shell55_top65_ballast', help='Vertical depth from the underside of the sleeper to the loaded surface above the top slab. Analysis metadata only; not added to the RC section depth.')
            with b:
                width = st.number_input('Train strip width (m)', min_value=.01, value=basis['track_width_m'], step=.1,
                    key='slab_shell55_top65_width', help='Width used for the equivalent area load in CSI; default project assumption 2.00 m.')
            with c:
                pressure = st.number_input('Nominal train UDL (kN/m²)', min_value=.01, value=basis['nominal_pressure_kpa'], step=1.,
                    key='slab_shell55_top65_pressure', help='Record the nominal pressure actually chosen for the CSI model. The project starting assumption is 75; it is not a universal code U20 equivalent.')
            st.caption('Keep the same four complete CSI exports. Strength forces must already contain the selected impact and load factors. No factor or ballast dispersion is applied here. For equivalent UDL, record the values used in your new CSI analysis; these entries do not regenerate its forces or qualify the train-load equivalence.')
        run = st.form_submit_button('Calculate Top slab', type='primary', use_container_width=True,
            key='slab_shell55_aashto62_calculate', disabled=package is None or error is not None)
    return run, {'method': method, 'ballast_mm': ballast, 'track_width_m': width,
                 'nominal_pressure_kpa': pressure}


def _cards(result):
    summary = result['summary'].set_index('Check')
    cards = []
    for label, title in [('Direct N–M · transverse', 'Transverse N–M'),
                         ('Direct N–M · longitudinal', 'Longitudinal N–M'),
                         ('Shear · transverse', 'One-way transverse'),
                         ('Shear · longitudinal', 'One-way longitudinal')]:
        row = summary.loc[label]
        cards.append({'title': title+' · D/C', 'value': number(row['Max D/C']),
            'detail': f'{row.Status} · {row.Case} / {row.Step}',
            'status': 'danger' if row.Status == 'FAIL' else 'warning' if row.Status == 'REVIEW' else 'ready'})
    render_metric_cards(cards)


def _mats(result):
    table = result['mat_envelopes']
    columns = ['Mat', 'Bar (mm)', 'Spacing (mm)', 'Section N–M D/C',
        'Tension-side shear tie D/C', 'Temperature D/C', 'Spacing D/C', 'Known checks']
    st.dataframe(table[columns], hide_index=True, width='stretch',
        column_config={c: st.column_config.NumberColumn(format='%.3f') for c in columns if 'D/C' in c})
    st.caption('N–M uses both physical mats. Top / bottom identify negative / positive bending cases; axial-dominant tension appears in both. Shear tie uses its actual tension mat. These checks do not add the two mats or U-dowels as slab Vs.')


def _proposal(result):
    proposal = result.get('reinforcement_proposal')
    if not isinstance(proposal, dict):
        return
    with st.expander('Suggested bar spacing · not applied', expanded=False):
        st.caption(f"Verification: {proposal['status']} · {proposal['trials']} trial(s) · "
            f"known reinforcement ratios {'within limits' if proposal['known_rebar_checks_satisfied'] else 'still exceed limits'}. "
            'Diameters and covers are held at the existing values.')
        columns = ['Mat', 'Bar (mm)', 'Current spacing (mm)', 'Proposed spacing (mm)',
            'Section N–M D/C', 'Tension-side shear tie D/C', 'Temperature D/C', 'Known checks']
        st.dataframe(proposal['mats'][columns], hide_index=True, width='stretch',
            column_config={c: st.column_config.NumberColumn(format='%.3f') for c in columns if 'D/C' in c})
        st.caption('The current charts and Summary use the applied project inputs. To use this proposal, revise the existing longitudinal / Slab mesh spacings and Calculate again. Proposals use the same retained vectors and support-face scope; they do not resolve shell coupling, anchorage or missing sources.')
        if proposal['concrete_shear_has_failures']:
            st.info('One-way concrete shear still exceeds its limit with the proposed bars. Review slab depth, concrete strength or the analysed load/support model. In-plane mesh is not added as slab Vs.')
        st.dataframe(proposal['shear'][['Check', 'Status', 'Max D/C', 'Case', 'Step', 'X (m)', 'Y (m)']],
            hide_index=True, width='stretch')


def _code_review(result):
    review=result.get('code_review')
    if not isinstance(review,dict):
        return
    st.info('Sectional shear / tie results apply outside finite girder and diaphragm reaction footprints. Local transfer inside those footprints remains REVIEW; its original slab-only indices are retained below. This is not a shear exemption or a complete deck PASS.')
    with st.expander('AASHTO applicability / Local transfer review', expanded=False):
        vectors=review['governing_vectors']
        columns=['Direction','Check','Region','Review status','D/C','OutputCase','X (m)','Y (m)']
        st.dataframe(vectors[columns],hide_index=True,width='stretch',
            column_config={'D/C':st.column_config.NumberColumn(format='%.3f')})
        st.caption('Local transfer rows retain the original sectional indices; their design status is REVIEW. The source masks and all eight concurrent actions are unchanged. Sectional numerical maxima and unresolved local-transfer regions must both be assessed.')
        st.markdown('**Governing tension-side shear ties**')
        ties=vectors.loc[vectors.Check.eq('tie')]
        columns=['Direction','Region','X (m)','Y (m)','M term (kN/m)','N term (kN/m)',
            'V term (kN/m)','Tie demand (kN/m)','Tie capacity (kN/m)','D/C']
        st.dataframe(ties[columns],hide_index=True,width='stretch')
        st.latex(r'T_{req}=\max[0,\;T_M+T_N+T_V],\quad T_M={|M_u|\over\phi_f d_v},\;T_N={N_u\over2\phi_c},\;T_V={|V_u|\over\phi_v}\cot\theta')
        st.caption('Tension positive, compression negative. Demand/capacity in kN/m. The existing four physical mats supply As fy; no U-dowel or second-mat shear credit is added.')
        st.markdown('**Code options and their evidence**')
        st.dataframe(review['eligibility'],hide_index=True,width='stretch')
        st.caption('AASHTO LRFD 2020: 5.7.1.2 / 5.7.3.1 local load paths, 5.7.3.5 maximum-moment limit, 5.7.3.2 support sections, 5.7.3.4.2-7 aggregate. No maximum-moment cap or dv shift is applied from force ratios or nominal UDL metadata alone.')
        st.markdown('**Selected signed section cuts · comparison only**')
        cuts=review['section_cuts']
        if len(cuts):
            columns=['Direction','Origin region','OutputCase','Section coordinate (m)','Cut side','Width (m)',
                'Source coverage','Available width (m)','Sectional shear D/C','Sectional tie D/C','Status']
            st.dataframe(cuts[[c for c in columns if c in cuts]],hide_index=True,width='stretch')
        for error in review['cut_errors']:
            st.caption(error)
        st.latex(r'R_{cut}=\int_a^b r(w)\,dw,\qquad r_{strip}=R_{cut}/(b-a)')
        st.caption('Signed line integration of all eight native components, at the same case/step. Width is at most 1 m and stops at physical contact boundaries; actual clipped width is reported. FE-edge sides remain separate. Any missing or excluded source gives incomplete coverage and no numeric sectional check. These selected cuts do not establish a full strip envelope or external-load equilibrium; they never replace charts, Summary or design status.')


def _coverage(result, link, analysis_engine=engine):
    with st.expander('Code scope / Details / Report', expanded=False):
        st.dataframe(result['reinforcement_summary'], hide_index=True, width='stretch')
        st.dataframe(result['clear_spacing'], hide_index=True, width='stretch')
        table = result['code_coverage'].copy()
        mask = table.Check.eq('Slab–girder interface / U-dowels')
        table.loc[mask, 'Coverage'] = 'LINKED · '+link['status']
        st.dataframe(table, hide_index=True, width='stretch')
        st.caption('AASHTO LRFD 9th Edition (2020). Required development lengths are references, not proof of available anchorage. Nxy/Mxy interaction, simultaneous biaxial shear, local D-regions, actual anchorage, fatigue and SLS remain separate checks. Agreed exclusions define the reviewed scope; they are not a code shear exemption.')
        link_signature = hashlib.sha256((link['status']+link['rows'].to_json(orient='split')).encode()).hexdigest()
        if st.button('Prepare compact Top slab report', key='slab_shell55_top65_prepare_report'):
            st.session_state['slab_shell55_top65_report'] = (result['fingerprint'], link_signature,
                analysis_engine.report_zip(result, interface=link))
        payload = st.session_state.get('slab_shell55_top65_report')
        if payload and len(payload) == 3 and payload[:2] == (result['fingerprint'], link_signature):
            st.download_button('Download Top slab report', payload[2], file_name='Top_Slab_'+analysis_engine.VERSION.replace('.', '-')+'_Report.zip',
                mime='application/zip', key='slab_shell55_top65_download_report')


def render(*, analysis_engine=engine):
    engine = analysis_engine
    render_page_header('Top slab · Reinforcement',
        'AASHTO LRFD 9th Edition (2020) · CSI shell forces · existing top / bottom mats',
        icon='SL', kicker='Analysis / Deck slab', badge=engine.VERSION, accent='blue')
    st.caption('Code-based ULS sections · eight concurrent shell components retained · imported forces ×1.00.')
    group = st.radio('Review group', GROUPS, horizontal=True, key='slab_shell55_shear64_group')
    if group == 'Punching shear':
        _areas()
    package = current_package(st.session_state)
    error = None
    try:
        inputs.steel_from_state(st.session_state)
        punching.config(st.session_state)
    except ValueError as exc:
        error = str(exc)
    run, basis = _load_form(package, error)
    if st.button('Shell import / required files', key='slab_shell55_aashto62_import'):
        st.session_state['_nav_active_workspace'] = 'Loads'
        st.session_state['_nav_loads_subpage'] = 'Slab Shell Results'
        st.rerun()
    if package is None:
        st.info('Import the four complete Excel export sets in Loads → Slab Shell Results. The same tables are used for the new equivalent-train-load analysis.')
    if error:
        st.warning(error)
    result = engine.current(st.session_state)
    if run:
        bar = st.progress(0., text='Checking native shell inputs…')
        try:
            engine.save_load_basis(st.session_state, basis)
            with st.spinner('Calculating AASHTO Top slab checks…'):
                result = engine.calculate(st.session_state,
                    progress=lambda value, text: bar.progress(value, text=text),
                    reuse=accepted.current(st.session_state))
            st.session_state[engine.RESULT_KEY] = result
            if 'top65_result' in result:
                from concrete_pmm_pro.analysis import slab_top65
                st.session_state[slab_top65.RESULT_KEY] = result['top65_result']
            if 'design66_result' in result:
                from concrete_pmm_pro.analysis import slab_design66
                st.session_state[slab_design66.RESULT_KEY] = result['design66_result']
            st.session_state[accepted.RESULT_KEY] = result['shear_result']
            st.session_state[sections.RESULT_KEY] = result['base_result']
            for key in ('slab_shell55_top65_report', 'slab_shell55_aashto62_csv_payload', 'slab_shell55_aashto63_faces_payload'):
                st.session_state.pop(key, None)
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            st.session_state.pop(engine.RESULT_KEY, None)
            result = None
            st.error('Top slab calculation unavailable: '+str(exc))
        finally:
            bar.empty()
    link = linked_results(st.session_state)
    if result is None:
        st.info('STALE — inputs changed; Calculate again.' if engine.RESULT_KEY in st.session_state else
            'NOT CALCULATED — press Calculate Top slab. Four existing reinforcement mats are reused; no second reinforcement input table is needed.')
        with st.expander('Existing slab inputs', expanded=False):
            from concrete_pmm_pro.ui.slab_shell56_workspace import _input_review
            _input_review()
        _interface(link)
        _case_studies()
        return
    _cards(result)
    st.caption(f"{result['design_rows']:,} retained native records · {result['excluded_rows']:,} excluded · "
        f"{len(result['support_faces']):,} support-face samples · ULS components: {result['component_status']} · "
        f"deck acceptance: {result['status']}.")
    basis = result['load_basis']
    detail = f" · ballast {basis['ballast_mm']:g} mm"
    if basis['method'] == 'equivalent_udl':
        detail += f" · nominal q={basis['nominal_pressure_kpa']:g} kN/m² over {basis['track_width_m']:g} m width"
    st.caption(engine.METHODS[basis['method']]+detail+' · '+result['load_basis_status']+'. Recorded load basis only; no force rescaling.')
    st.caption('Sectional ULS scope: Nxy/Mxy interaction, local support paths, actual anchorage and fatigue / SLS require their separate checks.')
    if result['incomplete']:
        st.warning('Incomplete native corner/case coverage remains REVIEW; missing values are not filled.')
    _mats(result)
    _code_review(result)
    _proposal(result)
    if not result['required_actions'].empty:
        with st.expander('Required actions', expanded=False):
            st.dataframe(result['required_actions'], hide_index=True, width='stretch')
    if group == 'Punching shear':
        if basis['method'] == 'equivalent_udl' and not result['punching']['areas']:
            st.info('The declared train load is a continuous area-load strip. One-way shear is calculated from CSI. No isolated punching footprint is implied by this UDL model; local concentrated loads / reactions require their physical footprints for a separate punching check.')
        _punching(result)
        _interface(link)
        _coverage(result, link, engine)
        _case_studies()
        return
    visible = [v for v in engine.VIEWS if
        v.startswith(('Shear ·', 'Flexural shear tie ·')) == (group == 'One-way shear')]
    if st.session_state.get('slab_shell55_aashto62_view') not in visible:
        st.session_state['slab_shell55_aashto62_view'] = visible[0]
    controls = st.columns([2, 1.25, 1])
    with controls[0]:
        view = st.selectbox('Result', visible, key='slab_shell55_aashto62_view')
    with controls[1]:
        cases = [ALL_CASES, *sorted(result['rows'].OutputCase.unique())]
        if st.session_state.get('slab_shell55_aashto62_case') not in cases:
            st.session_state['slab_shell55_aashto62_case'] = ALL_CASES
        case = st.selectbox('Load case', cases, key='slab_shell55_aashto62_case')
    with controls[2]:
        mode = st.selectbox('Chart', ['Plan map', 'Station D/C'], key='slab_shell55_top65_chart')
    adapted = engine.map_adapter(result, view)
    selected = element_envelope(adapted, view='Overall section', case=case)
    try:
        fig = plots.plan(result, adapted, view, case) if mode == 'Plan map' else plots.profile(adapted, view, case)
    except ValueError as exc:
        st.info(str(exc))
        fig = plots.plan(result, adapted, view, case)
    st.html('''<style>@media screen{
      .st-key-slab_top65_plot{overflow-x:auto;max-width:100%}
      .st-key-slab_top65_plot [data-testid="stPlotlyChart"]{min-width:860px}
    }</style>''')
    with st.container(key='slab_top65_plot'):
        st.plotly_chart(fig, width='stretch', key='slab_shell55_aashto62_plan',
            config={'displaylogo': False, 'toImageButtonOptions': {'format': 'png', 'width': 1440, 'height': 720, 'scale': 1.5}})
    st.caption('D/C=1 is the limit. Plan = retained actual corner/case maxima per element; grey = excluded / unresolved. Station D/C = known maximum at each physical station, with gaps and separate scope markers. No smoothing or averaging. Shear/tie include matching support-face samples. Filters do not change the all-case summary.')
    show = result['summary'].loc[result['summary'].Check.isin(visible)].copy()
    show['Case / step'] = show.Case+' / '+show.Step
    st.dataframe(show[['Check', 'Status', 'Max D/C', 'Case / step', 'X (m)', 'Y (m)', 'Failed nodes', 'Review nodes']],
        hide_index=True, width='stretch', column_config={c: st.column_config.NumberColumn(format='%.3f')
            for c in ['Max D/C', 'X (m)', 'Y (m)']})
    _trace(result, selected, view)
    _audit(result, selected, view)
    _interface(link)
    _coverage(result, link, engine)
    _case_studies()
