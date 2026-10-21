"""Punching load areas and actual candidate paths on the accepted plan map."""
import math
import numpy as np
import plotly.graph_objects as go
from concrete_pmm_pro.visualization.slab_shell56 import plan_figure
from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability
from concrete_pmm_pro.visualization import slab_print72 as printing


def figure(result,case='All punching cases'):
    base=result['base_result']
    rows=base['rows'].copy(deep=False).assign(**{'Field D/C':np.nan,'Status':'REVIEW','Combined N–M–V status':'REVIEW'})
    fig=plan_figure({**base,'rows':rows})
    fig.update_layout(title_text='Punching shear · AASHTO LRFD 2020',uirevision='SLAB.PUNCHING64:'+case)
    p=result['punching'];records=p['rows']
    if not records.empty and case!='All punching cases':records=records.loc[records.Case.eq(case)]
    drawn=set()
    for area in p['areas']:
        name=area['Area'];path=p['paths'].get(name)
        if path is None:continue
        selected=records.loc[records.Area.eq(name)] if not records.empty else records
        finite=selected['D/C'].dropna() if len(selected) else []
        dc=float(max(finite)) if len(finite) else math.nan
        status='FAIL' if len(selected) and selected.Status.eq('FAIL').any() else 'REVIEW' if not len(selected) or selected.Status.eq('REVIEW').any() else 'PASS'
        color={'FAIL':printing.FAIL,'REVIEW':'#a38b60','PASS':printing.RESPONSE}[status]
        bounded=len(selected) and selected['Demand basis'].str.contains('upper bound',regex=False).any()
        points=path['points']@path['basis']
        label='Critical perimeter'
        fig.add_trace(go.Scatter(x=points[:,0],y=points[:,1],mode='lines',line={'color':color,'width':3},
            name=label,legendgroup='perimeter',showlegend=label not in drawn,
            hovertemplate=name+' · '+path['type']+'<extra></extra>'))
        drawn.add(label)
        centre=np.array([area['X (m)'],area['Y (m)']])@path['basis'].T
        l,b=area['L (mm)']/2000,area['B (mm)']/2000
        xy=(np.array([[-l,-b],[l,-b],[l,b],[-l,b],[-l,-b]])+centre)@path['basis']
        label='Loaded area'
        fig.add_trace(go.Scatter(x=xy[:,0],y=xy[:,1],mode='lines',fill='toself',fillcolor='rgba(184,213,223,.25)',
            line={'color':'#24364b','width':2},name=label,legendgroup='loaded',showlegend=label not in drawn,
            hovertemplate=name+'<extra></extra>'))
        drawn.add(label)
        fig.add_trace(go.Scatter(x=[area['X (m)']],y=[area['Y (m)']],mode='markers',
            marker={'symbol':'diamond-open','size':12,'color':color},showlegend=False,
            hovertemplate=name+'<br>'+status+(f'<br>D/C upper bound {dc:.3f}' if bounded and np.isfinite(dc) else f'<br>D/C {dc:.3f}' if np.isfinite(dc) else '<br>No qualified demand')+'<extra></extra>'))
    return apply_global_plot_readability(fig)
