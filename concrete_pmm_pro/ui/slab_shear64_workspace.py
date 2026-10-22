"""Compact one-way / punching review, with read-only existing interface status."""
from __future__ import annotations
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from concrete_pmm_pro.analysis import slab_shear64 as engine, slab_aashto63 as base, slab_punching64 as punching
from concrete_pmm_pro.analysis import slab_shell56 as inputs
from concrete_pmm_pro.io.slab_shell_import import current_package
from concrete_pmm_pro.ui.commercial import render_page_header,render_metric_cards
from concrete_pmm_pro.ui.slab_aashto63_workspace import number,_trace,_audit,_case_studies
from concrete_pmm_pro.ui.slab_interface64 import linked_results
from concrete_pmm_pro.visualization.slab_shell56 import ALL_CASES,plan_figure,element_envelope

GROUPS=['One-way shear','Punching shear','Reinforcement']


def _review_oneway():
    st.session_state['slab_shell55_shear64_group']='One-way shear'


def _automatic_punching_inputs():
    from concrete_pmm_pro.ui.slab_punching78_workspace import inputs as bound_inputs
    bound_inputs()


def _areas(*,expanded=None):
    try:
        areas=punching.config(st.session_state)
        signature=punching.signature(st.session_state)
    except ValueError as exc:
        st.warning('Correct punching-area inputs: '+str(exc));areas=[];signature=None
    with st.expander('Punching load / reaction areas · optional',expanded=not areas if expanded is None else expanded):
        st.caption('Enter the physical area where load reaches the slab: centre X/Y in the imported global coordinates, L along the bridge, B transverse. Dimensions are at the slab surface after any load dispersion. Materials, thickness and reinforcement levels are read automatically.')
        frame=pd.DataFrame(areas,columns=punching.COLUMNS)
        if not areas:
            # A real, typed blank row is editable without finding the table's
            # add-row control. It is not a manufactured load-area definition.
            frame=pd.DataFrame({c:pd.Series([None],dtype='object' if c=='Area' else 'float64')
                for c in punching.COLUMNS})
            st.caption('Fill the blank row: X/Y in m and L/B in mm. Area name and Vu may be left blank.')
        revision=int(st.session_state.get('slab_shell55_punch75_editor_revision',0))
        editor_key='slab_shell55_punch64_editor'+(f'_{revision}' if revision else '')
        with st.form('slab_shell55_punch64_form'):
            edited=st.data_editor(frame,hide_index=True,num_rows='dynamic',width='stretch',
                key=editor_key,column_config={
                    'Area':st.column_config.TextColumn('Area',help='Unique load-area name, e.g. P1. Blank names are assigned automatically.'),
                    **{c:st.column_config.NumberColumn(c,format='%.3f',
                        help='Required physical coordinate or loaded-area dimension.') for c in punching.COLUMNS[1:5]},
                    punching.COLUMNS[-1]:st.column_config.NumberColumn(punching.COLUMNS[-1],min_value=0.,format='%.3f',
                        help='Optional independently established factored design shear across the critical perimeter, in kN; not an unfactored axle load. Blank uses an automatic conservative shell-force bound.')})
            save=st.form_submit_button('Apply load areas')
        if save:
            try:updated=punching.normalise(edited)
            except ValueError as exc:st.error(str(exc))
            else:
                if not updated and not areas:
                    st.warning('No load areas applied. Enter centre X/Y (m) and positive L/B (mm) in the blank row, then Apply. Vu is optional.')
                else:
                    metadata=dict(st.session_state.get('project_metadata') or {})
                    metadata[punching.CONFIG_KEY]={'version':1,'areas':updated}
                    st.session_state['project_metadata']=metadata
                    # Rebase the editor after committing: replaying the old
                    # added/deleted row delta could duplicate or remove areas.
                    st.session_state['slab_shell55_punch75_editor_revision']=revision+1
                    st.session_state['slab_shell55_punch75_notice']={
                        'signature':punching.signature(st.session_state),'count':len(updated)}
                    st.rerun()
        st.caption('Blank Vu: automatic upper-bound demand, with no assumed spatial simultaneity of moving-load extrema. Passing the bound is sufficient for the direct shear component; an exceeded bound remains REVIEW. Enter direct factored Vu only when independently known. No punching patch is invented from a stress peak.')
    # The expander can close after a successful Apply; keep its acknowledgement
    # visible outside it, including on the rerun that refreshes Save Project JSON.
    notice=st.session_state.get('slab_shell55_punch75_notice')
    if isinstance(notice,dict) and notice.get('signature')==signature:
        count=notice['count']
        if count:
            st.success(f"Applied {count} load area{'s' if count!=1 else ''}. Use Calculate below to calculate or refresh Punching shear.")
        else:
            st.info('Load areas cleared. Punching shear has no defined load area. Use Calculate below to update the results.')


def _interface(link):
    with st.expander('Interface shear · linked from Flexure',expanded=False):
        st.dataframe(link['rows'],hide_index=True,width='stretch')
        st.caption(link['scope'])
        st.caption('Source: Analysis → ULS Strength → Flexure → Final — Composite → Calculate Flexure. This page reads current result hashes and checks every stored interface row. It does not run Flexure, reuse stale PASS, or extend one girder result to the whole bridge.')
        if st.button('Open Final Composite Flexure',key='slab_shell55_shear64_open_flexure'):
            st.session_state['_nav_active_workspace']='Analysis'
            st.session_state['_nav_analysis_subpage']='ULS Strength'
            st.session_state['beam_girder_uls_lazy_check']='Flexure'
            st.session_state['beam_girder_composite_flexure_stage']='Final — Composite'
            st.session_state['igird_flexure31_view']='Interface shear'
            st.rerun()


def _coverage(result,link):
    with st.expander('AASHTO coverage / remaining checks',expanded=False):
        table=result['code_coverage'].copy()
        mask=table.Check.eq('Two-way / punching shear')
        table.loc[mask,'Coverage']=result.get('punching_screen78',result['punching'])['status']
        table.loc[mask,'Basis / remaining action']='Adopted CSI forces and actual thickness at each source point; local indices and explicit physical-perimeter checks are separate. Depth changes and moment transfer remain guarded.'
        mask=table.Check.eq('Slab–girder interface / U-dowels')
        table.loc[mask,'Coverage']='LINKED · '+link['status']
        table.loc[mask,'Basis / remaining action']='Existing Final Composite longitudinal interface result for the listed members only; separate joint opening/roll acceptance is not inferred.'
        st.dataframe(table,hide_index=True,width='stretch')
        st.caption('Punching moment transfer, overlapping loaded areas, irregular/opened or inclined slabs, variable-thickness critical surfaces, local support paths and full shell interaction require their applicable detailed checks. Overall deck acceptance remains REVIEW REQUIRED.')


def _punching(result):
    if 'punching_screen78' in result:
        from concrete_pmm_pro.ui.slab_punching78_workspace import render as bound_render
        bound_render(result)
        if not result['punching']['rows'].empty:
            with st.expander('Explicit physical load areas · perimeter checks', expanded=False):
                _physical_punching(result)
        if result.get('track_distribution', {}).get('config', {}).get('enabled'):
            with st.expander('Track distribution · geometry', expanded=False):
                from concrete_pmm_pro.visualization.slab_track77 import figure as track_figure
                from concrete_pmm_pro.visualization.slab_print72 import export_config
                st.plotly_chart(track_figure(result), width='stretch', key='slab_shell55_track77_geometry', config=export_config())
        return
    _physical_punching(result)


def _physical_punching(result):
    p=result['punching']
    distribution=result.get('track_distribution')
    track_active=bool(distribution and distribution['config']['enabled'])
    if p['rows'].empty:
        # A grey deck is not a calculated punching result. The automatic input
        # review explains the actual model and the missing local-load scope.
        if track_active:
            from concrete_pmm_pro.visualization.slab_track77 import figure as track_figure
            from concrete_pmm_pro.visualization.slab_print72 import export_config
            from concrete_pmm_pro.ui.slab_track77_workspace import trace as track_trace
            st.plotly_chart(track_figure(result),width='stretch',key='slab_shell55_punch64_plan',config=export_config())
            track_trace(distribution)
            st.caption('Continuous train-load influence and actual girder flange contacts are calculated. There is no isolated punching D/C in this result; the map is a geometry / load-path view, not a strength acceptance map.')
        else:
            st.caption('No isolated punching D/C is available in the current result. The automatic review above describes the load-model scope.')
        return
    else:
        case=st.selectbox('Punching case to review',['All punching cases',*list(dict.fromkeys(p['rows'].Case))],key='slab_shell55_punch64_case')
        table=p['rows'] if case=='All punching cases' else p['rows'].loc[p['rows'].Case.eq(case)]
        st.dataframe(table[['Area','Case','Perimeter type','Demand basis','Vu (kN)','phiVn (kN)','D/C','Status','Reason']],
            hide_index=True,width='stretch',column_config={c:st.column_config.NumberColumn(format='%.3f') for c in ['Vu (kN)','phiVn (kN)','D/C']})
    from concrete_pmm_pro.visualization.slab_punching64 import figure
    if track_active:
        from concrete_pmm_pro.visualization.slab_track77 import figure
    from concrete_pmm_pro.visualization.slab_print72 import export_config
    st.plotly_chart(figure(result,case),width='stretch',key='slab_shell55_punch64_physical_plan',
        config=export_config())
    if track_active:
        from concrete_pmm_pro.ui.slab_track77_workspace import trace as track_trace
        track_trace(distribution)
    st.caption('Available loaded-area paths and critical perimeters are shown on the imported slab. Fully supported areas outside slab-only scope have no punching D/C; they are not PASS. Free edges contribute no resisting perimeter. An exceeded automatic demand bound remains REVIEW. Existing connection/end/peak omissions cannot be reconstructed into a passing automatic demand.')
    with st.expander('Calculation trace / Equations',expanded=False):
        st.latex(r'V_n=\min\left(0.063+{0.126\over\beta_c},\,0.126\right)\lambda\sqrt{f_c^\prime}\,b_0d_v\quad\mathrm{(ksi,in,kips)}')
        st.latex(r'\beta_c={\max(L,B)\over\min(L,B)},\quad\phi=0.90,\quad V_s=0,\quad\mathrm{offset}\ge0.5d_v')
        st.latex(r'V_{u,upper}=\sum_{segments}\ell\,\max_{active\ corners,\,steps}|Q_n|,\qquad D/C_{upper}={V_{u,upper}\over\phi V_n}')
        st.caption('AASHTO LRFD 2020 5.12.8.6.1 / 5.12.8.6.3. Each cut uses the relevant V13/V23 after physical-axis rotation. Opposite signs are not cancelled to create a favourable punching force. Direct user Vu is already factored. In-plane mesh and U legs are not credited as punching shear reinforcement.')
        if not p['rows'].empty:st.dataframe(p['rows'],hide_index=True,width='stretch')
    if not p['rows'].empty:
        st.download_button('Download punching checks',p['rows'].to_csv(index=False).encode('utf-8-sig'),
            file_name='Deck_Slab_Punching64.csv',mime='text/csv',key='slab_shell55_punch64_csv')


def render():
    render_page_header('Slab Reinforcement','AASHTO LRFD 2020 · one-way / punching shear · existing four reinforcement mats',
        icon='SL',kicker='Analysis / Deck slab',badge='SLAB.SHEAR64',accent='blue')
    st.caption('Code-based component checks. One-way shear includes its tension-side reinforcement check. Punching uses explicit load areas. Existing girder interface results are linked by current inputs; full deck acceptance remains REVIEW REQUIRED.')
    group=st.radio('Review group',GROUPS,horizontal=True,key='slab_shell55_shear64_group')
    if group=='Punching shear':
        _automatic_punching_inputs()
        _areas(expanded=False)
    package=current_package(st.session_state)
    error=None
    try:inputs.steel_from_state(st.session_state);punching.config(st.session_state)
    except ValueError as exc:error=str(exc)
    cols=st.columns([2,1])
    with cols[0]:run=st.button('Calculate Slab Reinforcement',type='primary',use_container_width=True,key='slab_shell55_aashto62_calculate',disabled=package is None or error is not None)
    with cols[1]:
        if st.button('Shell import / required files',use_container_width=True,key='slab_shell55_aashto62_import'):
            st.session_state['_nav_active_workspace']='Loads';st.session_state['_nav_loads_subpage']='Slab Shell Results';st.rerun()
    if package is None:st.warning('Import the current complete shell package in Loads → Slab Shell Results.')
    if error:st.warning(error)
    result=engine.current(st.session_state)
    if run:
        bar=st.progress(0.,text='Checking AASHTO slab inputs…')
        try:
            with st.spinner('Calculating slab checks…'):
                result=engine.calculate(st.session_state,progress=lambda value,text:bar.progress(value,text=text),reuse=base.current(st.session_state))
            st.session_state[engine.RESULT_KEY]=result
            st.session_state[base.RESULT_KEY]=result['base_result']
            for key in ('slab_shell55_aashto62_csv_payload','slab_shell55_aashto63_faces_payload'):st.session_state.pop(key,None)
        except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
            st.session_state.pop(engine.RESULT_KEY,None);result=None;st.error('Slab calculation unavailable: '+str(exc))
        finally:bar.empty()
    link=linked_results(st.session_state)
    if result is None:
        st.info('STALE — inputs changed; Calculate again. Valid one-way results can be reused when only punching areas change.' if engine.RESULT_KEY in st.session_state else 'NOT CALCULATED — press Calculate Slab Reinforcement.')
        if group!='Punching shear':
            from concrete_pmm_pro.ui.slab_shell56_workspace import _input_review
            _input_review()
        _interface(link);_case_studies();return
    summary=result['summary'].set_index('Check')
    cards=[]
    for label,title in [('Shear · transverse','One-way transverse D/C'),('Shear · longitudinal','One-way longitudinal D/C')]:
        r=summary.loc[label];cards.append({'title':title,'value':number(r['Max D/C']),'detail':f'{r.Status} · {r.Case} / {r.Step}',
            'status':'danger' if r.Status=='FAIL' else 'warning' if r.Status=='REVIEW' else 'ready'})
    cards.extend([{'title':'Punching shear','value':result['punching']['status'],'detail':f"{len(result['punching']['areas'])} defined loaded areas",'status':'danger' if result['punching']['status']=='FAIL' else 'ready' if result['punching']['status'].startswith('PASS') else 'warning'},
        {'title':'Interface · linked','value':link['status'],'detail':f"{link['members']} listed girder(s) · read-only",'status':'danger' if link['status']=='FAIL' else 'ready' if link['status']=='PASS' else 'warning'}])
    render_metric_cards(cards)
    st.caption(f"{result['design_rows']:,} retained native records · {result['excluded_rows']:,} excluded · one-way base reused: {'yes' if result['base_reused'] else 'no'} · overall deck acceptance: REVIEW REQUIRED.")
    _interface(link);_coverage(result,link)
    if result['incomplete']:st.warning('Incomplete source coverage remains REVIEW.')
    if group=='Punching shear':_punching(result);_case_studies();return
    visible=[v for v in engine.VIEWS if (v.startswith('Shear ·') or v.startswith('Flexural shear tie ·'))==(group=='One-way shear')]
    if st.session_state.get('slab_shell55_aashto62_view') not in visible:st.session_state['slab_shell55_aashto62_view']=visible[0]
    controls=st.columns([2,1])
    with controls[0]:view=st.selectbox('Result to review',visible,key='slab_shell55_aashto62_view')
    with controls[1]:case=st.selectbox('Load case to review',[ALL_CASES,*sorted(result['rows'].OutputCase.unique())],key='slab_shell55_aashto62_case')
    with st.expander('Top / Bottom reinforcement · code checks',expanded=False):st.dataframe(result['reinforcement_summary'],hide_index=True,width='stretch')
    adapted=engine.map_adapter(result,view)
    selected=element_envelope(adapted,view='Overall section',case=case)
    fig=plan_figure(adapted,view='Overall section',case=case)
    if (view.startswith('Shear ·') or view.startswith('Flexural shear tie ·')) and any(s['Direction']==('Transverse' if view.endswith('transverse') else 'Longitudinal') for s in result['supports']):
        segments=[]
        for support in result['supports']:
            direction='Transverse' if view.endswith('transverse') else 'Longitudinal'
            if support['Direction']!=direction:
                continue
            for sign in (-1,1):
                offset=sign*support['half_width']*support['normal']
                segments.extend([support['a']+offset,support['b']+offset,[np.nan,np.nan]])
        xy=np.asarray(segments)
        fig.add_trace(go.Scatter(x=xy[:,0],y=xy[:,1],mode='lines',line={'color':'#246c9a','width':1},
            hoverinfo='skip',name='Support contact faces',connectgaps=False))
    fig.update_layout(title_text=view+' · '+('all ULS cases' if case==ALL_CASES else case),
        uirevision=f'AASHTO63:{view}:{case}',meta={'slab_version':engine.VERSION,
            'aggregation':'maximum retained actual corner/case; agreed geometry and one-pass peak exclusions',
            'code':'AASHTO LRFD 2020','full_deck_acceptance':False})
    st.html('''<style>@media screen{
      .st-key-slab_aashto62_plot{overflow-x:auto;max-width:100%}
      .st-key-slab_aashto62_plot [data-testid="stPlotlyChart"]{min-width:860px}
    }</style>''')
    with st.container(key='slab_aashto62_plot'):
        st.plotly_chart(fig,width='stretch',key='slab_shell55_aashto62_plan',
            config={'displaylogo':False,'toImageButtonOptions':{'format':'png','width':1440,'height':720,'scale':1.5}})
    st.caption('Map = maximum retained actual corner/case per element; shear/tie also include corresponding physical support-face samples. No D/C averaging. D/C=1 is the limit. Grey includes excluded nodes and unresolved local support regions. Solid blue lines show the corresponding support contact faces; dotted lines and shaded ends show the agreed exclusions. Filters do not change the all-case summary.')
    show=result['summary'].loc[result['summary'].Check.isin(visible)].copy()
    show['Case / step']=show.Case+' / '+show.Step
    st.dataframe(show[['Check','Status','Max D/C','Case / step','X (m)','Y (m)','Failed nodes','Review nodes']],
        hide_index=True,width='stretch',column_config={k:st.column_config.NumberColumn(format='%.3f') for k in ['Max D/C','X (m)','Y (m)']})
    _trace(result,selected,view)
    _audit(result,selected,view)
    _case_studies()
