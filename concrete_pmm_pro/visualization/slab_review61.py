"""Labelled sensitivity maps using the accepted nominal chart style."""
from concrete_pmm_pro.analysis import slab_review61 as review
from concrete_pmm_pro.visualization.slab_shell56 import plan_figure,ALL_CASES


def plan(nominal,study,*,basis,view,case=ALL_CASES):
    plotted=review.map_result(nominal,study,basis)
    fig=plan_figure(plotted,view=view,case=case)
    fig.update_layout(title={'text':f'{view} · {basis} · REVIEW','x':.5,'xanchor':'center'},
        meta={**fig.layout.meta,'sensitivity_version':review.VERSION,'study_basis':basis,'design_acceptance':False})
    for trace in fig.data:
        if trace.name and trace.name.startswith('Gov.'):
            trace.name=trace.name.replace('Gov.','Study max',1)
            trace.hovertemplate=trace.hovertemplate.replace('Governing corner','Study maximum')
        if basis==review.ZONES and trace.name=='Source details':
            trace.text=[text.replace('Corner Zone mean:','Zone sample centroid:')+'<br>Retained-sample area mean · REVIEW' for text in trace.text]
    if basis==review.FILTERED:
        peaks=study['source'].loc[study['source'][review.PEAK]]
        if case!=ALL_CASES:peaks=peaks.loc[peaks.OutputCase.eq(case)]
        peaks=peaks.drop_duplicates('Joint')
        fig.add_scatter(x=peaks['X (m)'],y=peaks['Y (m)'],mode='markers',
            marker={'symbol':'x','size':5,'color':'#704099'},name='Peaks excluded',
            text=peaks.Joint,hovertemplate='Study-excluded joint %{text}<extra></extra>')
    return fig
