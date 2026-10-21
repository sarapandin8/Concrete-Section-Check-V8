"""Compact staged deflection review; one Calculate, one selected figure."""
import pandas as pd
import streamlit as st

from concrete_pmm_pro.serviceability import girder_deflect69 as engine
from concrete_pmm_pro.visualization.girder_deflect69 import figure
from concrete_pmm_pro.ui.commercial import render_page_header, render_metric_cards

STAGES = ['Transfer stage','Construction stage','Service stage']


def render(*, build_curves, span_m):
    code_label=str(st.session_state.get('project_code_edition') or st.session_state.get('code_edition') or 'Project criterion')
    render_page_header('SLS Deflection / Camber',code_label+' · instantaneous elastic stage response',
        icon='δ',kicker='Analysis / Serviceability',badge=engine.VERSION,accent='blue')
    st.caption('Positive δ = upward camber; negative δ = downward. LL+IM is checked as an increment, separately from net prestress camber.')
    config = engine.settings(st.session_state)
    with st.form('girder_deflect69_calculation'):
        with st.expander('Deflection criteria / Live-load source',expanded=False):
            st.selectbox('LL deflection criterion',list(engine.PROFILES),index=list(engine.PROFILES).index(config['profile']),
                format_func=engine.PROFILES.get,key='girder_deflect69_ui_profile')
            a,b = st.columns(2)
            with a:
                live = st.number_input('Service LL+IM per girder (kN/m)',min_value=0.,value=config['live_udl_kN_m'],
                    placeholder='Use existing LL component, or enter a line load',key='girder_deflect69_ui_live',
                    help='Optional uniform line load assigned to THIS girder, including impact once. Do not enter total bridge/track pressure or factored ULS load. Blank is unavailable when the existing load model has no LL component.')
            with b:
                custom = st.number_input('Custom LL limit (mm)',min_value=.001,value=config['custom_limit_mm'],
                    placeholder='Only for custom criterion',key='girder_deflect69_ui_custom')
            a,b = st.columns(2)
            with a:
                transfer = st.number_input('Transfer |δ| tolerance (mm)',min_value=.001,value=config['transfer_limit_mm'],
                    placeholder='Optional project tolerance',key='girder_deflect69_ui_transfer')
            with b:
                construction = st.number_input('Construction |δ| tolerance (mm)',min_value=.001,value=config['construction_limit_mm'],
                    placeholder='Optional project tolerance',key='girder_deflect69_ui_construction')
            st.caption('Railway L/1500 with a 30 mm cap is the project criterion used here. AASHTO L/800 is an optional highway LL+IM criterion. Neither is assigned to transfer/construction camber. Blank stage tolerances remain response-only REVIEW.')
        run = st.form_submit_button('Calculate deflection / camber',type='primary',width='stretch',key='girder_deflect69_calculate')
    if run:
        st.session_state[engine.SETTINGS_KEY] = {'profile':st.session_state['girder_deflect69_ui_profile'],
            'custom_limit_mm':custom,'live_udl_kN_m':live,'transfer_limit_mm':transfer,'construction_limit_mm':construction}
        try:
            with st.spinner('Calculating stage responses and LL criterion…'):
                result = engine.calculate(st.session_state,build_curves(),span_m)
            st.session_state[engine.RESULT_KEY] = result
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            st.session_state.pop(engine.RESULT_KEY,None)
            st.error('Deflection calculation unavailable: '+str(exc))
    result = engine.current(st.session_state)
    if result is None:
        st.info('STALE — inputs changed; Calculate again.' if engine.RESULT_KEY in st.session_state else 'NOT CALCULATED — press Calculate deflection / camber.')
        return
    ll = result['summary'].loc[lambda f:f.Check.eq('LL+IM increment')].iloc[0]
    render_metric_cards([
        {'title':'LL+IM check','value':ll.Status,'detail':result['live_source'],'status':'danger' if ll.Status=='Preview FAIL' else 'ready' if ll.Status=='Preview PASS' else 'warning'},
        {'title':'LL deflection','value':f"{ll['Demand (mm)']:.3f} mm" if pd.notna(ll['Demand (mm)']) else 'Unavailable',
            'detail':f'D/C {ll.Utilization:.3f}' if pd.notna(ll.Utilization) else 'No numeric LL check','status':'info'},
        {'title':'LL limit','value':f"{result['limit_mm']:.2f} mm" if result['limit_mm'] else 'Review only','detail':result['limit_label'],'status':'info'},
        {'title':'Full deflection scope','value':result['status'],'detail':'Long-term and refined stage response remain separate','status':'danger' if result['status']=='Preview FAIL' else 'warning'},
    ])
    st.dataframe(result['summary'][['Stage','Check','Response','Demand (mm)','Limit (mm)','Utilization','Status']],
        hide_index=True,width='stretch',column_config={c:st.column_config.NumberColumn(format='%.3f') for c in ['Demand (mm)','Limit (mm)','Utilization']})
    if not result['live_available']:
        st.warning('The generated bridge stage-load model has no live-load component. The former coincident service curves did not demonstrate a zero train-load deflection. LL+IM remains REVIEW until a service LL source is supplied.')
    st.caption('Source: generated stage loads, not imported CSI displacements or integrated CSI SLS moments. Constant EI / midspan Pe are retained from the existing model; debond-dependent Pe(x), end-section EI, stage Ec, creep/shrinkage and cracked stiffness require refined analysis.')
    stage = st.radio('Stage',STAGES,horizontal=True,key='girder_deflect69_ui_stage')
    with st.container(key='girder_deflect69_plot'):
        st.plotly_chart(figure(result,stage),width='stretch',key='girder_deflect69_chart')
    if stage == 'Service stage':
        st.caption('Red dashed line = negative LL+IM increment limit. Compare it with the LL+IM increment trace, not the sustained/net camber. Identical completion/sustained elastic curves are shown once; no long-term curve is fabricated.')
    else:
        st.caption('Stage response only unless a project |δ| tolerance is supplied. Any dashed ± lines are project tolerances, not universal code camber limits. Full span 0–L; no smoothing or endpoint clipping.')
    with st.expander('Calculation trace / Equations / Source audit',expanded=False):
        st.markdown('**Deflection component audit**')
        st.dataframe(result['source_audit'],hide_index=True,width='stretch')
        st.latex(r'\delta_{LL}(x)=-\frac{w_{LL}x(L^3-2Lx^2+x^3)}{24E_c I_{comp}},\qquad \delta_{LL,max}=\frac{5w_{LL}L^4}{384E_c I_{comp}}')
        st.latex(r'\delta_{net+LL}(x)=\delta_{sustained,elastic}(x)+\delta_{LL}(x)')
        st.caption('w in N/mm (=kN/m), x and L in mm, Ec in MPa, I in mm⁴, δ in mm. Source stage camber uses equivalent midspan Pe·e; precast loads remain on precast EI and post-composite increments use transformed EI.')
        st.write(result['limit_basis'])
        st.download_button('Download deflection audit',engine.report_zip(result),
            file_name='SLS_DEFLECT69_Audit.zip',mime='application/zip',key='girder_deflect69_download')
