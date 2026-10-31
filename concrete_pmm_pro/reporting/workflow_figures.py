"""Read-only figures for the shared workflow calculation reports."""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .bg40_figures import COLORS,finish,section

RATIOS=('dcr','utilization','D/C value','Utilization value','Utilization','Overall D/C value',
    'Governing D/C value','Stress D/C value','Transverse D/C value','Longitudinal D/C value','D/C')
DEMAND_CAPACITY={
    'Flexure':(('Demand kN-m','Mux'),('Capacity kN-m','φMn kN-m'),'|Moment| (kN·m)'),
    'Shear':(('Abs demand kN','Demand kN','Vuy'),('φVn kN','phiVn kN'),'|Shear| (kN)'),
    'Torsion':(('Abs demand kN-m','Demand kN-m','Tu'),('phiTn kN-m','φTn kN-m'),'|Torque| (kN·m)')}


def number_column(data,choices):
    return next((k for k in choices if k in data and pd.to_numeric(data[k],errors='coerce').notna().any()),None)


def plottable(data): return number_column(data,RATIOS) is not None


def beam_plottable(data):
    return plottable(data) or number_column(data,('Demand kN-m','Abs demand kN','Demand kN','Abs demand kN-m')) is not None


def utilization(data,title):
    ratios=[c for c in RATIOS if c in data and pd.to_numeric(data[c],errors='coerce').notna().any()]
    components=[c for c in ratios if c in ('Stress D/C value','Transverse D/C value','Longitudinal D/C value')]
    ratios=components or ratios[:1]
    if not ratios: return None
    xkey=next((k for k in ('Station s (m)','Station x (m)','x (m)','Station (m)') if k in data),None)
    identity=[k for k in ('Case','Case Name','combo_name','Stage','Girder','Section face') if k in data]
    figure=go.Figure()
    groups=list(data.groupby(identity,dropna=False,sort=False)) if identity and xkey else [((),data)]
    for gi,(group,rows) in enumerate(groups):
        suffix=' | '.join(str(x) for x in (group if isinstance(group,tuple) else (group,)))
        for ri,ratio in enumerate(ratios):
            if xkey:
                rows=rows.sort_values(xkey,kind='stable'); x=rows[xkey]
                mode='markers' if 'Section face' in data else 'lines+markers'
            else:
                labels=[k for k in ('combo_name','Stage','Case','Case Name','Check','point_name') if k in rows]
                x=rows[labels].astype(str).agg(' | '.join,axis=1) if labels else [f'Row {i+1}' for i in range(len(rows))]
                mode='markers'
            figure.add_trace(go.Scatter(x=x,y=pd.to_numeric(rows[ratio],errors='coerce'),mode=mode,
                name=(suffix+' | ' if suffix else '')+ratio,connectgaps=False,
                line={'color':COLORS[(gi+ri)%len(COLORS)],'width':2.5},marker={'size':8}))
    figure.add_hline(y=1.,line_dash='dash',line_color='#c62828',annotation_text='Check limit = 1.0',annotation_position='top right')
    figure.update_xaxes(title=xkey or 'Stored case / check point')
    figure.update_yaxes(title='Utilization D/C',rangemode='tozero')
    figure.update_layout(meta={'combined_vector_created':False,'source_cases':{f'C{i+1}':str(v) for i,v in enumerate(data[identity[0]].drop_duplicates())} if identity else {}})
    return finish(figure,title)


def beam(data,spec):
    check=spec['plot_check']
    if check not in DEMAND_CAPACITY: return utilization(data,spec['title'])
    demands,capacities,unit=DEMAND_CAPACITY[check]
    demand,capacity=number_column(data,demands),number_column(data,capacities)
    if not demand: return utilization(data,spec['title'])
    xkey=next((k for k in ('Station x (m)','Station s (m)','Governing x') if k in data),None)
    if not xkey: return utilization(data,spec['title'])
    data=data.copy(); data['_x']=pd.to_numeric(data[xkey].astype(str).str.replace(' m','',regex=False),errors='coerce')
    casekey=next((k for k in ('Case','Case Name') if k in data),None)
    groups=list(data.groupby(casekey,dropna=False,sort=False)) if casekey else [('',data)]
    has_ratio=plottable(data)
    figure=make_subplots(rows=2 if has_ratio else 1,cols=1,shared_xaxes=True,vertical_spacing=.18 if has_ratio else 0.)
    for i,(case,rows) in enumerate(groups):
        rows=rows.sort_values('_x',kind='stable'); prefix=str(case)+' | ' if case else ''
        for col,label,dash in ((demand,'|Demand|','solid'),(capacity,'|Resistance|','dash')):
            if col:
                figure.add_trace(go.Scatter(x=rows['_x'],y=pd.to_numeric(rows[col],errors='coerce').abs(),
                    name=prefix+label,mode='lines+markers',connectgaps=False,
                    line={'color':COLORS[i%len(COLORS)],'dash':dash,'width':2.5},marker={'size':6}),row=1,col=1)
        if has_ratio:
            ratio=number_column(rows,RATIOS)
            if ratio:
                figure.add_trace(go.Scatter(x=rows['_x'],y=pd.to_numeric(rows[ratio],errors='coerce'),
                    name=prefix+'D/C',mode='lines+markers',connectgaps=False,
                    line={'color':COLORS[i%len(COLORS)],'width':2.5},marker={'size':6}),row=2,col=1)
    figure.update_yaxes(title=unit,row=1,col=1)
    if has_ratio:
        figure.add_hline(y=1.,line_dash='dash',line_color='#c62828',row=2,col=1)
        figure.update_yaxes(title='Utilization D/C',rangemode='tozero',row=2,col=1)
    figure.update_xaxes(title='Station x (m)',row=2 if has_ratio else 1,col=1)
    figure.update_layout(meta={'combined_vector_created':False,'source_cases':{f'C{i+1}':str(c) for i,(c,_) in enumerate(groups)}})
    return finish(figure,spec['title'],height=850)


def stress_points(data,title):
    stress=number_column(data,('total_stress_MPa','stress_MPa','Stress MPa','Actual stress (MPa)'))
    if not stress: return utilization(data,title)
    figure=go.Figure(); casekey=next((k for k in ('combo_name','Case','Case Name','Stage') if k in data),None)
    groups=list(data.groupby(casekey,dropna=False,sort=False)) if casekey else [('',data)]
    point=next((k for k in ('point_name','Fiber','Point','Station s (m)') if k in data),None)
    for i,(case,rows) in enumerate(groups):
        x=rows[point].astype(str) if point else [str(n+1) for n in range(len(rows))]
        figure.add_trace(go.Scatter(x=x,y=pd.to_numeric(rows[stress],errors='coerce'),mode='markers',
            name=str(case)+' | stress',marker={'size':10,'color':COLORS[i%len(COLORS)]}))
        limit=number_column(rows,('limit_MPa','Limit stress (MPa)'))
        if limit:
            values=pd.to_numeric(rows[limit],errors='coerce')
            if limit=='limit_MPa' and 'stress_type' in rows: values=values.where(~rows['stress_type'].astype(str).str.lower().eq('compression'),-values.abs())
            figure.add_trace(go.Scatter(x=x,y=values,mode='markers',name=str(case)+' | applicable signed limit',
                marker={'size':11,'color':'#c62828','symbol':'line-ew','line':{'width':2}}))
    figure.add_hline(y=0.,line_color='#64748b',line_width=1)
    figure.update_xaxes(title=point or 'Stored check point'); figure.update_yaxes(title='Signed concrete stress (MPa)')
    return finish(figure,title)


def pmm(state,spec):
    result=state.get('rc_pmm_result') or state.get('pmm_result')
    if result is None: return None
    from concrete_pmm_pro.analysis.result_models import pmm_result_to_display_dataframe
    data=pmm_result_to_display_dataframe(result)
    if data.empty: return None
    z=data['phiPn_capped_N'].fillna(data['phiPn_N']) if 'phiPn_capped_N' in data else data['phiPn_N']
    fig=go.Figure(go.Scatter3d(x=data['phiMnx_Nmm']/1e6,y=data['phiMny_Nmm']/1e6,z=z/1e3,
        mode='markers',name='Stored factored PMM points',marker={'size':3.5,'color':COLORS[0],'opacity':.65}))
    dc=state.get('rc_demand_capacity_result') or state.get('demand_capacity_summary')
    if dc is not None:
        rows=getattr(dc,'results',[])
        fig.add_trace(go.Scatter3d(x=[r.Mux_Nmm/1e6 for r in rows],y=[r.Muy_Nmm/1e6 for r in rows],z=[r.Pu_N/1e3 for r in rows],
            mode='markers+text',text=[r.combo_name for r in rows],name='ULS demand points',marker={'size':6,'color':'#c62828'}))
    axes={k:{'title':{'text':title,'font':{'size':22}},'tickfont':{'size':20}} for k,title in
        (('xaxis','φMnx / Mux (kN·m)'),('yaxis','φMny / Muy (kN·m)'),('zaxis','φPn / Pu (kN)'))}
    fig.update_layout(scene={**axes,'aspectmode':'cube','camera':{'eye':{'x':1.35,'y':1.35,'z':.85},'projection':{'type':'orthographic'}}})
    return finish(fig,spec['title'],height=800)


def crossbeam(state,spec):
    from concrete_pmm_pro.ui import analysis_page as ap
    result=state.get(spec['source_key']) or {}; rows=pd.DataFrame(result.get('rows') or []); fibers=pd.DataFrame(result.get('fiber_rows') or [])
    case=spec.get('case')
    if case is not None:
        if not rows.empty and 'Case' in rows: rows=rows[rows.Case.astype(str).eq(str(case))].copy()
        if not fibers.empty and 'Case' in fibers: fibers=fibers[fibers.Case.astype(str).eq(str(case))].copy()
    check=spec['plot_check']; segments=state.get('crossbeam_ui1_segment_layout_rows') or []; supports=result.get('support_footprints') or []
    common=dict(segment_rows=segments,support_footprints=supports,pt_end_zone_settings=result.get('pt_end_zone_settings'),
        construction_method=str(state.get('crossbeam_ptloss3b1_construction_method') or 'Precast Segmental'),member_length_m=float(state.get('crossbeam_ui1_length_m') or 0.))
    if check=='Flexure':
        demand=rows.rename(columns={'Station s (m)':'Station x (m)','Case':'Case Name','M3 kN-m':'Mux','P kN':'Nu','V2 kN':'Vuy','T kN-m':'Tu'})
        return ap._make_crossbeam_uls_flexure_figure(demand,rows,**common)
    if check=='Shear': return ap._make_crossbeam_uls_shear_figure(ap._crossbeam_shear_demand_plot_rows(rows),rows,pd.DataFrame(),pd.DataFrame(),**common)
    if check=='Torsion': return ap._make_crossbeam_uls_torsion_figure(rows,supports,segment_rows=segments,
        pt_end_zone_settings=result.get('pt_end_zone_settings'),construction_method=common['construction_method'],member_length_m=common['member_length_m'])
    if check=='Shear + Torsion': return ap._make_crossbeam_uls_combined_vt_component_figure(rows,supports,segments,
        component=spec['component'],pt_end_zone_settings=common['pt_end_zone_settings'],
        construction_method=common['construction_method'],member_length_m=common['member_length_m'])
    if check.startswith('At '): return ap._make_crossbeam_transfer_stress_figure(rows,fibers,case_name=str(case),
        member_length_m=common['member_length_m'],column_rows=state.get('crossbeam_ptloss3b1_column_rows') or [],stage_title=check,joint_transfer_no_tension=check=='At Transfer')
    if 'deflection' in check.lower(): return ap._make_crossbeam_sls_deflection_figure(result,stage=spec['stage'],case_name=str(case),
        member_length_m=common['member_length_m'],column_rows=state.get('crossbeam_ptloss3b1_column_rows') or [])
    return utilization(rows,spec['title'])


def crossbeam_system(state,spec):
    # The UI elevation helper canonicalizes global session inputs. Keep report
    # drawing pure, preserving the supplied segment and column references.
    fig=go.Figure()
    for i,row in enumerate(state.get('crossbeam_ui1_segment_layout_rows') or []):
        start,end=float(row.get('x_start_m',row.get('s_start (m)',0.))),float(row.get('x_end_m',row.get('s_end (m)',0.)))
        fig.add_trace(go.Scatter(x=[start,end],y=[0.,0.],mode='lines',line={'width':24,'color':COLORS[i%len(COLORS)]},
            name=str(row.get('Segment') or i+1)+' | '+str(row.get('Section ID') or 'Source section')))
        fig.add_annotation(x=(start+end)/2,y=.15,text=str(row.get('Segment') or i+1),showarrow=False)
    for row in state.get('crossbeam_ptloss3b1_column_rows') or []:
        x=float(row.get('Station s (m)',0.))
        fig.add_trace(go.Scatter(x=[x,x],y=[-.55,-.06],mode='lines',line={'width':10,'color':'#64748b'},name=str(row.get('Column ID') or 'Column reference')))
    length=float(state.get('crossbeam_ui1_length_m') or 0.)
    fig.update_xaxes(title='Member station s (m)',range=[-length*.04,length*1.04]); fig.update_yaxes(visible=False,range=[-.75,.35])
    fig.update_layout(meta={'source':'Stored section layout and column references','restraints_inferred':False})
    return finish(fig,spec['title'])


def build(state,spec):
    kind=spec['plot']
    if kind=='section': return section(state)
    if kind=='system':
        from .bg40_figures import system
        return system(state)
    if kind=='crossbeam_system': return crossbeam_system(state,spec)
    if kind=='crossbeam_section':
        from concrete_pmm_pro.crossbeam.section_library import build_geometry_for_definition
        from concrete_pmm_pro.visualization.section_plot import create_section_preview
        return finish(create_section_preview(build_geometry_for_definition(spec['definition'])),spec['title'])
    if kind=='pmm': return pmm(state,spec)
    if kind=='crossbeam': return crossbeam(state,spec)
    if kind=='deflection82':
        from concrete_pmm_pro.serviceability.girder_deflect70 import current
        from concrete_pmm_pro.visualization.girder_deflect70 import figure
        result=current(state)
        if result is None: return None
        fig=figure(result,spec['stage'],spec.get('girder')); fig.update_layout(title={'text':spec['title']}); return fig
    data=pd.DataFrame(spec.get('data') or [])
    if kind=='stress_points': return stress_points(data,spec['title'])
    if kind=='beam': return beam(data,spec)
    return utilization(data,spec['title'])
