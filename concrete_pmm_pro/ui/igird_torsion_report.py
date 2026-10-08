"""Report charts from current cached I-girder station resistance, never solvers."""
from __future__ import annotations

import re
import pandas as pd


def current_torsion_packages(state):
    from concrete_pmm_pro.ui.igird_uls_report import current_check_packages
    return current_check_packages(state, 'Torsion')


def make_package_figure(state,package,*,member,code_label,case=None):
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.ui.igird_case_review import controlling_result
    from concrete_pmm_pro.ui.igird_vt_workspace import make_torsion_case_figure
    result = package['result']
    frame = result['torsion_check_df']
    if case is None:
        case = (controlling_result(frame,'Torsion').get('row') or {}).get('Case')
    if case is None:
        return None
    return make_torsion_case_figure(package['rows'],frame,case=case,
        code_label=code_label,span_m=ap._beam_uls_span_length_from_state(state,is_building=False),
        diagram=result.get('torsion_diagram_capacity_df'),
        boundary=result.get('torsion_boundary_capacity_df'),member_name=member)


def make_current_torsion_report_figure(state,*,member=None,code_label):
    packages = current_torsion_packages(state)
    if not packages:
        return None
    if member is not None and member not in packages:
        return None
    member = member if member is not None else next(iter(packages))
    return make_package_figure(state,packages[member],member=member,code_label=code_label)


def render_torsion_report_charts(state,*,code_label):
    import streamlit as st
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.ui.igird_case_review import controlling_result
    if state.get('section_preset_key') != 'parametric_i_girder':
        return
    with st.expander('Torsion report chart — stored results',expanded=False):
        packages = current_torsion_packages(state)
        if not packages:
            st.info('No current I-girder torsion chart is available. Calculate Torsion in Analysis for the current inputs.')
            return
        member = st.selectbox('Girder for report chart',list(packages),key='igird_torsion_report_member')
        package = packages[member]
        frame = package['result']['torsion_check_df']
        control = controlling_result(frame,'Torsion')
        controlling_case = (control.get('row') or {}).get('Case')
        cases = frame['Case'].dropna().drop_duplicates().tolist()
        case = st.selectbox('Load case for report chart',cases,
            index=cases.index(controlling_case) if controlling_case in cases else 0,
            key='igird_torsion_report_case')
        st.caption(f'Controlling stored load case: {controlling_case or "—"}. The chart uses this girder and the selected case only; overall FAIL/REVIEW decisions remain in the stored checks.')
        fig = make_package_figure(state,package,member=member,code_label=code_label,case=case)
        ap._render_beam_uls_browser_plotly_figure(fig,interactive=True)
        st.caption('The exported image includes girder, load case, units, stored decision counts and explanatory notes. Qualified below-threshold / zero-Tu station resistance is taken from the same cached diagram used in Analysis.')
        if st.button('Create report chart PNG',key='igird_torsion_report_prepare'):
            with st.spinner('Creating report chart image…'):
                image = fig.to_image(format='png',width=1440,height=560,scale=2)
            name = re.sub(r'[^A-Za-z0-9_-]+','_',member+'_'+str(case)).strip('_')
            st.download_button('Download report chart PNG',data=image,
                file_name='torsion_'+name+'.png',mime='image/png',
                on_click='ignore',key='igird_torsion_report_download')
