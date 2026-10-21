"""One full-span deflection figure using the shared SLS chart grammar."""
from html import escape

import numpy as np
import plotly.graph_objects as go

from concrete_pmm_pro.visualization.igird_sls53 import COLORS, apply_sls_layout
from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability


def figure(result, stage):
    span = result['span_m']
    data = result['curves'].loc[result['curves'].Stage.eq(stage)]
    fig = go.Figure()
    for index,(name,group) in enumerate(data.groupby('Curve',sort=False)):
        live = group.Role.iloc[0] == 'Live increment'
        fig.add_trace(go.Scatter(x=group['Station x (m)'],y=group['Deflection (mm)'],name=name,
            mode='lines+markers',line={'color':COLORS['bottom'] if live else COLORS['top'] if index==0 else COLORS['tension'],
                'width':2.6,'dash':'dash' if live else 'solid'},marker={'size':4},connectgaps=False,cliponaxis=False,
            hovertemplate=escape(name)+'<br>x=%{x:.3f} m<br>δ=%{y:.3f} mm<extra></extra>'))
    if stage == 'Service stage':
        limit = result['limit_mm']
        if limit is not None:
            fig.add_trace(go.Scatter(x=[0,span],y=[-limit,-limit],name=f'LL limit · {limit:.2f} mm',
                mode='lines',line={'color':COLORS['compression'],'width':2.2,'dash':'dash'},
                hovertemplate='LL+IM increment limit<br>δ=%{y:.3f} mm<extra></extra>'))
        if not result['live_available']:
            fig.add_annotation(x=.5,y=.08,xref='paper',yref='paper',showarrow=False,
                text='LL+IM source missing · no LL curve or PASS',font={'size':12,'color':'#946200'},bgcolor='white')
        governor = data.loc[data.Role.eq('Live increment')]
    else:
        key = 'transfer_limit_mm' if stage == 'Transfer stage' else 'construction_limit_mm'
        limit = result['settings'][key]
        if limit is not None:
            for sign in (-1,1):
                fig.add_trace(go.Scatter(x=[0,span],y=[sign*limit]*2,name=f'Project ±{limit:.2f} mm',
                    showlegend=sign==1,mode='lines',line={'color':COLORS['compression'],'width':2.2,'dash':'dash'},
                    hovertemplate='Project stage tolerance<br>δ=%{y:.3f} mm<extra></extra>'))
        governor = data
    if len(governor):
        row = governor.loc[governor['Deflection (mm)'].abs().idxmax()]
        fig.add_trace(go.Scatter(x=[row['Station x (m)']],y=[row['Deflection (mm)']],name='Governing response',
            mode='markers',marker={'symbol':'diamond-open','size':12,'color':COLORS['governing'],'line':{'width':2}},
            showlegend=False,cliponaxis=False,hovertemplate='Governing plotted response<br>x=%{x:.3f} m<br>δ=%{y:.3f} mm<extra></extra>'))
    fig.add_hline(y=0,line_color='#64748b',line_width=1.2)
    fig.update_layout(template='plotly_white',height=560,
        title={'text':escape(stage.replace(' stage',''))+' · deflection / camber<br><sup>'+escape(result['code_edition'])+' · instantaneous</sup>','x':.5,'xanchor':'center'},
        margin={'l':76,'r':36,'t':84,'b':110},font={'family':'Arial, sans-serif','size':13,'color':'#334155'},
        xaxis={'title':'Distance along member (m)','range':[0,span],'showgrid':True,'zeroline':False,'automargin':True},
        yaxis={'title':'Deflection δ (mm)','showgrid':True,'zeroline':False,'automargin':True},hovermode='x unified',
        uirevision=result['fingerprint']+':'+stage,meta={'version':result['version'],'stage':stage,'positive_direction':'upward',
            'limit_applies_to':'LL increment' if stage=='Service stage' else 'Optional project absolute-response tolerance',
            'live_source_available':result['live_available'],'full_deflection_acceptance':False})
    apply_global_plot_readability(fig)
    apply_sls_layout(fig)
    # All legends remain short; 4 entries wrap cleanly on compact desktops.
    fig.update_layout(legend={'orientation':'h','entrywidth':190,'itemwidth':35,'y':-.23})
    return fig
