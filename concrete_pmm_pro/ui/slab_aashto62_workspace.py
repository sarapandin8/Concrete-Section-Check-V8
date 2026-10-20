"""Compact AASHTO directional slab checks; research is explicitly opt-in."""
from __future__ import annotations

import math
import pandas as pd
import streamlit as st

from concrete_pmm_pro.analysis import slab_aashto62 as engine
from concrete_pmm_pro.analysis import slab_shell56 as inputs
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED, REASON
from concrete_pmm_pro.analysis.slab_review61 import PEAK
from concrete_pmm_pro.io.slab_shell_import import current_package
from concrete_pmm_pro.ui.commercial import render_page_header, render_metric_cards
from concrete_pmm_pro.visualization.slab_shell56 import ALL_CASES, plan_figure, element_envelope


def number(value, digits=3):
    return f'{float(value):,.{digits}f}' if value is not None and math.isfinite(float(value)) else 'REVIEW'


def _case_studies():
    with st.expander('Case studies / Legacy shell model', expanded=False):
        st.caption('Optional N–M sandwich-field, resultant-shear and zone-average studies. These do not replace the AASHTO directional component results above.')
        if st.checkbox('Open legacy research workspace', key='slab_shell55_aashto62_research_open'):
            from concrete_pmm_pro.ui.slab_shell56_workspace import render
            render()


def _trace(result, selected, view):
    column,_=engine.VIEWS[view]
    known=selected.loc[selected[column].notna()]
    if known.empty:
        return
    row=known.loc[known[column].idxmax()]
    with st.expander('Calculation trace / Equations', expanded=False):
        st.markdown(f"**{view} · {row['OutputCase']} / {row['StepType']} · {row.name} · joint {row['Joint']}**")
        st.caption(f"X={row['X (m)']:.5f} m, Y={row['Y (m)']:.5f} m · h={row['Thickness (mm)']:.2f} mm · source row components stay together.")
        ledger=[]
        for label,(dc,status) in engine.VIEWS.items():
            ledger.append({'Check':label,'D/C':row[dc],'Status':row[status]})
        st.dataframe(pd.DataFrame(ledger),hide_index=True,width='stretch',column_config={'D/C':st.column_config.NumberColumn(format='%.3f')})
        st.markdown('**Native shell axes → physical reinforcement axes**')
        st.dataframe(pd.DataFrame([
            {'Axes':'CSI local','N1 (kN/m)':row.F11,'N2 (kN/m)':row.F22,'N12 (kN/m)':row.F12,
             'M1 (kN·m/m)':row.M11,'M2 (kN·m/m)':row.M22,'M12 (kN·m/m)':row.M12,'V1 (kN/m)':row.V13,'V2 (kN/m)':row.V23},
            {'Axes':'Longitudinal / transverse','N1 (kN/m)':row.Nx,'N2 (kN/m)':row.Ny,'N12 (kN/m)':row.Nxy,
             'M1 (kN·m/m)':row.Mx,'M2 (kN·m/m)':row.My,'M12 (kN·m/m)':row.Mxy,'V1 (kN/m)':row.Vx,'V2 (kN/m)':row.Vy}
        ]),hide_index=True,width='stretch')
        st.caption('V1/V2 are transverse shear through faces normal to the first/second reinforcement direction; both act normal to the slab. M11 bends in direction 1 although its physical moment axis is local 2. Local 3 and the physical top/bottom faces are checked. No force-reference translation is applied.')
        st.markdown('**Directional sectional shear · AASHTO 5.7.3.3 / 5.7.3.4**')
        trace=[]
        for label,*_ in engine.AXES:
            trace.append({'Direction':label,'Procedure':row[label+' procedure'],'Tension mat':row[label+' tension mat'],
                'As (mm²/m)':row[label+' As tension (mm²/m)'],'dv (mm)':row[label+' dv (mm)'],
                'sx (mm)':row[label+' sx (mm)'],'sxe (mm)':row[label+' sxe (mm)'],
                'εs raw':row[label+' strain raw'],'εs used':row[label+' strain used'],
                'β':row[label+' beta'],'θ (deg)':row[label+' theta (deg)'],
                'Vn (kN/m)':row[label+' Vn (kN/m)'],'φVn (kN/m)':row[label+' phiVn (kN/m)'],
                'Shear D/C':row[label+' shear D/C'],'Tie D/C':row[label+' tie D/C']})
        st.dataframe(pd.DataFrame(trace),hide_index=True,width='stretch')
        st.latex(r'd_v=\max[0.9(h-c_{s,tension}),\;0.72h],\qquad V_s=V_p=0')
        st.latex(r'\varepsilon_s={\max(|M_u|/d_v,|V_u|)+0.5N_u+|V_u|\over E_sA_{s,tension}}')
        st.caption('Use N, M, V and As from the same direction. Units in the strain equation: N and mm. Negative strain is taken as zero. A zero-tensile-strength cracked-section assumption doubles strain if both nominal bending faces are in tension. General-procedure strain above 0.006 remains REVIEW; it is not silently clipped to obtain a passing result.')
        st.latex(r'\beta=2,\;\theta=45^\circ\quad\text{when 5.7.3.4.1 applies}')
        st.latex(r'\beta={4.8\over1+750\varepsilon_s}{51\over39+s_{xe}/25.4},\quad\theta=29+3500\varepsilon_s')
        st.latex(r'\phi V_n\,[\mathrm{kN/m}]=0.90\,(0.0316\sqrt{6.894757293})\,\beta\sqrt{f_c^\prime[\mathrm{MPa}]}\,d_v[\mathrm{mm}]')
        st.caption('One metre normal-weight RC strip; the 0.25 f′c bv dv ceiling also applies. General branch uses no vertical shear reinforcement. Actual qualifying mesh-layer distances define sx≤dv; ag=0 gives no unreported aggregate-size credit. In-plane mesh and girder U-dowels are not automatically slab shear stirrups.')
        st.latex(r'T_{req}=\max\left[0,{|M_u|\over\phi_f d_v}+{N_u\over2\phi_c}+{|V_u|\over\phi_v}\cot\theta\right],\quad (D/C)_{tie}={T_{req}\over A_sf_y}')
        st.caption('5.7.3.5-1 tension-side flexural shear tie, φf=0.90, φc=0.75, φv=0.90, Vs=Vp=0. This does not add the full shear force to both shell faces. Provided bar area is a full-development sectional basis; development/termination remains a separate detailing check.')
        st.markdown('**Direct N–M section · AASHTO 5.6.2 / 5.6.3.2.5**')
        st.latex(r'\varepsilon_{cu}=0.003,\quad a=\beta_1c,\quad C=\alpha_1 f_c^\prime A_{block},\quad f_s=\min(E_s\varepsilon_t,f_y)')
        st.latex(r'(N_r,M_r)=\phi(\varepsilon_t)(N_n,M_n),\quad (D/C)_{NM}=1/\lambda,\quad (\lambda N_u,\lambda M_u)\in\partial\mathcal R')
        st.caption('Actual top/bottom bar levels and areas; tension-only steel credit; displaced concrete removed; φ=0.75–0.90 from tensile strain. The radial ratio scales N and M together. This direct directional check uses Nx/Mx or Ny/My; Nxy/Mxy transfer is retained as a separate shell-coupling review, not omitted from the reported scope.')
        st.dataframe(pd.DataFrame([{'Direction':d,'N boundary (kN/m)':row[d+' N boundary (kN/m)'],
            'M boundary (kN·m/m)':row[d+' M boundary (kN·m/m)'],'φ':row[d+' phi boundary'],
            'c (mm)':row[d+' c boundary (mm)'],'D/C':row[d+' N–M D/C']} for d,*_ in engine.AXES]),hide_index=True,width='stretch')


def _audit(result, selected, view):
    with st.expander('Exclusions / Source audit', expanded=False):
        st.caption(f"{result['source_rows']:,} imported Top Slab records · {result['design_rows']:,} checked · {result['geometry_excluded_rows']:,} connection/end records excluded · {result['peak_excluded_rows']:,} isolated-peak records excluded.")
        st.caption('Project exclusions are applied before checking: native I-girder lines, finite diaphragm lines, full-width physical end-to-bearing zones, then the unchanged REVIEW61 one-pass peak rule. No D/C threshold, iterative trimming or zone-average substitution is used. This project review policy does not certify that omitted FEM actions are erroneous or that excluded regions pass design.')
        st.dataframe(result['exclusion_counts'],hide_index=True,width='stretch')
        ends=result['connections'].get('end_zones',{})
        if ends.get('active'):
            st.dataframe(pd.DataFrame(ends['zones']),hide_index=True,width='stretch')
        else:
            st.info('Bearing end zones are inactive in the current inputs; no bearing offsets were guessed.')
        st.dataframe(result['connections']['lines'].drop(columns=['ID'],errors='ignore'),hide_index=True,width='stretch')
        st.caption('Peak rule: same case/step, ≥4 retained one-ring neighbours, opposing collinear pair, strict local maximum, magnitude/median >2 and modified score >3.5. Whole source vectors are omitted together. Neighbours are not re-screened after removing peaks.')
        st.dataframe(result['peak_ledger'].head(30),hide_index=True,width='stretch')
        st.dataframe(result['coverage'],hide_index=True,width='stretch')
        st.download_button('Download all-case check summary',result['summary'].to_csv(index=False).encode('utf-8-sig'),
            file_name='Deck_Slab_AASHTO62_Summary.csv',mime='text/csv',key='slab_shell55_aashto62_summary_csv')
        export=selected.reset_index().copy()
        keep=['AreaElem','Joint','OutputCase','StepType','X (m)','Y (m)','Thickness (mm)',
            'Map excluded','Map incomplete','Excluded records',*dict(engine.VIEWS.values()).keys()]
        export['View']=view
        st.download_button('Download current map envelope',export[[c for c in [*keep,'View'] if c in export]].to_csv(index=False).encode('utf-8-sig'),
            file_name='Deck_Slab_AASHTO62_Map.csv',mime='text/csv',key='slab_shell55_aashto62_map_csv')
        # Large source exports are explicitly prepared once, never serialized
        # merely because an expander exists on a Streamlit rerun.
        token='slab_shell55_aashto62_csv_payload'
        if st.button('Prepare complete source / exclusions CSV',key='slab_shell55_aashto62_prepare_csv'):
            st.session_state[token]=(result['fingerprint'],result['rows'].to_csv(index=False).encode('utf-8-sig'))
        saved=st.session_state.get(token)
        if saved and saved[0]==result['fingerprint']:
            st.download_button('Download complete source / exclusions CSV',saved[1],file_name='Deck_Slab_AASHTO62_Source.csv',mime='text/csv',key='slab_shell55_aashto62_source_csv')
    with st.expander('Axes / Reinforcement / Code scope', expanded=False):
        st.dataframe(result['axes'],hide_index=True,width='stretch')
        steel=result['steel']
        st.dataframe(pd.DataFrame({'Mat':inputs.GROUPS,'Bar (mm)':steel.diameter,
            'Spacing (mm)':steel.spacing,'As (mm²/m)':steel.area,'fy (MPa)':steel.fy,
            'Bar centre from corresponding face (mm)':steel.centre}),hide_index=True,width='stretch')
        st.write(result['scope'])
        st.caption('Native retained corner checks are used. AASHTO 5.7.3.2 support-face/dv sections depend on load introduction and nearby concentrated loads; line/end exclusions do not establish those conditions. Full deck acceptance is not inferred from separate directional PASS values. Project railway demands are retained; no highway-deck shear exemption is applied.')


def render():
    render_page_header('Slab Reinforcement','AASHTO LRFD 2020 · longitudinal / transverse sections · existing top and bottom reinforcement',
        icon='SL',kicker='Analysis / Deck slab',badge='AASHTO sections',accent='blue')
    st.caption('Directional component checks. Shell coupling, support sections, anchorage and full deck acceptance remain separate. Agreed connection/end/peak exclusions are applied before calculation.')
    package=current_package(st.session_state)
    error=None
    try:
        inputs.steel_from_state(st.session_state)
    except ValueError as exc:
        error=str(exc)
    cols=st.columns([2,1])
    with cols[0]:
        run=st.button('Calculate Slab Reinforcement',type='primary',use_container_width=True,
            key='slab_shell55_aashto62_calculate',disabled=package is None or error is not None)
    with cols[1]:
        if st.button('Shell import / required files',use_container_width=True,key='slab_shell55_aashto62_import'):
            st.session_state['_nav_active_workspace']='Loads'
            st.session_state['_nav_loads_subpage']='Slab Shell Results'
            st.rerun()
    if package is None:
        st.warning('Import the current complete shell package in Loads → Slab Shell Results.')
    if error:
        st.warning(error)
    result=engine.current(st.session_state)
    if run:
        bar=st.progress(0.,text='Recovering geometry, axes and agreed exclusions…')
        try:
            with st.spinner('Calculating AASHTO directional sections…'):
                result=engine.calculate(st.session_state,progress=lambda value,text:bar.progress(value,text=text))
            st.session_state[engine.RESULT_KEY]=result
            st.session_state.pop('slab_shell55_aashto62_csv_payload',None)
        except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
            st.session_state.pop(engine.RESULT_KEY,None)
            result=None
            st.error('Slab calculation unavailable: '+str(exc))
        finally:
            bar.empty()
    if result is None:
        st.info('STALE — inputs changed; calculate again.' if engine.RESULT_KEY in st.session_state else
            'NOT CALCULATED — press Calculate Slab Reinforcement to display the directional checks.')
        from concrete_pmm_pro.ui.slab_shell56_workspace import _input_review
        _input_review()
        _case_studies()
        return
    summary=result['summary'].set_index('Check')
    cards=[]
    for label,title in [('Shear · transverse','Transverse shear D/C'),('Shear · longitudinal','Longitudinal shear D/C'),
                        ('Direct N–M · transverse','Direct transverse N–M D/C'),('Direct N–M · longitudinal','Direct longitudinal N–M D/C')]:
        r=summary.loc[label]
        cards.append({'title':title,'value':number(r['Max D/C']),
            'detail':f"{r.Status} · {r.Case} / {r.Step}",
            'status':'danger' if r.Status=='FAIL' else 'warning' if r.Status=='REVIEW' else 'ready'})
    render_metric_cards(cards)
    st.caption(f"{result['design_rows']:,} retained records · {result['excluded_rows']:,} excluded · calculation {result['seconds']:.2f} s · full deck acceptance: REVIEW REQUIRED.")
    if result['incomplete']:
        st.warning('Incomplete source coverage. Missing corner/case groups remain REVIEW and cannot become a passing envelope.')
    controls=st.columns([2,1])
    with controls[0]:
        view=st.selectbox('Result to review',list(engine.VIEWS),key='slab_shell55_aashto62_view')
    with controls[1]:
        case=st.selectbox('Load case to review',[ALL_CASES,*sorted(result['rows'].OutputCase.unique())],key='slab_shell55_aashto62_case')
    adapted=engine.map_adapter(result,view)
    selected=element_envelope(adapted,view='Overall section',case=case)
    fig=plan_figure(adapted,view='Overall section',case=case)
    fig.update_layout(title_text=view+' · '+('all ULS cases' if case==ALL_CASES else case),
        uirevision=f'AASHTO62:{view}:{case}',meta={'slab_version':engine.VERSION,
            'aggregation':'maximum retained actual corner/case; agreed geometry and one-pass peak exclusions',
            'code':'AASHTO LRFD 2020','full_deck_acceptance':False})
    st.html('''<style>@media screen{
      .st-key-slab_aashto62_plot{overflow-x:auto;max-width:100%}
      .st-key-slab_aashto62_plot [data-testid="stPlotlyChart"]{min-width:860px}
    }</style>''')
    with st.container(key='slab_aashto62_plot'):
        st.plotly_chart(fig,width='stretch',key='slab_shell55_aashto62_plan',
            config={'displaylogo':False,'toImageButtonOptions':{'format':'png','width':1440,'height':720,'scale':1.5}})
    st.caption('Map = maximum retained corner/case per element. No D/C averaging. D/C=1 is the limit; colours use logarithmic spacing. Grey means excluded or unresolved. Dotted lines and shaded ends show the agreed geometric exclusions. Graph filters do not change the all-case summary.')
    show=result['summary'].copy()
    show['Case / step']=show.Case+' / '+show.Step
    st.dataframe(show[['Check','Status','Max D/C','Case / step','X (m)','Y (m)','Failed nodes','Review nodes']],
        hide_index=True,width='stretch',column_config={k:st.column_config.NumberColumn(format='%.3f') for k in ['Max D/C','X (m)','Y (m)']})
    _trace(result,selected,view)
    _audit(result,selected,view)
    _case_studies()
