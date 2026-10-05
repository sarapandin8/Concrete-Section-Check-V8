"""Actual user-derived Final-Composite model; no hypothetical steel/anchorage.
Scientific previews use exact production Plotly coordinates, not screenshots.
"""
import copy, hashlib, json, math, os, sys, time
from pathlib import Path
import pandas as pd
REPO=Path(os.environ.get('CSP_QA_REPO',Path(__file__).resolve().parents[1]))
OUT=Path(os.environ.get('CSP_QA_OUT',REPO/'qa/evidence/igird_shearcomp1'))
OUT.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(REPO))
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui import igird_vt_workspace as workspace
from concrete_pmm_pro.analysis.igird_shear_support import support_basis
model=REPO/'examples/I_Girder_20m_IGIRDER_SHEARCOMP1_FinalComposite_bearing400.json'
state={};apply_project_to_session_state(project_from_json(model.read_text()),state)
source=state['beam_uls_loads_table'].copy(deep=True)
assert len(source)==80
params=copy.deepcopy(state['section_parameters']);materials=copy.deepcopy(state['rebar_materials'])
route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
started=time.perf_counter()
result=ap._beam_uls_calculate_selected_check(state,source,selected_check='Shear + Torsion',strength_route=route)
seconds=time.perf_counter()-started
pd.testing.assert_frame_equal(source,state['beam_uls_loads_table'],check_exact=True)
assert params==state['section_parameters'] and materials==state['rebar_materials']
assert not params['Be_strength_verified'] and not materials
assert result['shear_critical_section_df'].empty
assert len(ap._beam_uls_shear_design_rows_for_governing(result['shear_check_df']))==80
frames={}
for key,value in result.items():
    if isinstance(value,pd.DataFrame):
        value.to_csv(OUT/('actual_source_'+key+'.csv'),index=False)
        frames[key]={'rows':len(value),'status':value['Status'].value_counts().to_dict() if 'Status' in value else {}}
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import plotly.io as pio
for name in ('Shear','Torsion'):
    check=result['shear_check_df' if name=='Shear' else 'torsion_check_df']
    diagram=result['shear_diagram_capacity_df' if name=='Shear' else 'torsion_diagram_capacity_df']
    figures={}
    for case in source['Case Name'].unique():
        selected=check.loc[check['Case'].eq(case)]
        selected_diagram=diagram.loc[diagram['Case'].eq(case)]
        demands=source.loc[source['Case Name'].eq(case)]
        if name=='Shear':
            fig=ap._make_beam_uls_shear_capacity_figure(demands,selected,
                code_label='AASHTO LRFD 9th (2020)',compact_csi_legend=True,
                member_length_m=20,source_context_df=source,diagram_capacity_df=selected_diagram)
            fig.data=tuple(t for t in fig.data if t.name not in {'φVc','Critical x'})
        else:
            fig=ap._make_beam_uls_torsion_capacity_figure(demands,selected,
                code_label='AASHTO LRFD 9th (2020)',member_length_m=20,
                source_context_df=source,diagram_capacity_df=selected_diagram)
            fig.data=tuple(t for t in fig.data if t.name not in {'±φTcr','±0.25φTcr'})
        for trace in fig.data:
            if str(trace.name).startswith('Gov.'):trace.showlegend=False
        figures[case]=fig
    canvas,axes=plt.subplots(2,2,figsize=(14,8.5),dpi=130,sharex=True)
    html=['<!doctype html><html><head><meta charset="utf-8"></head><body><h2>'+name+' — actual input, bearing CL x=0.4 / 19.6 m</h2><p>Final-Composite numerical screening. Unverified longitudinal material, effective width and interface action remain REVIEW. Grey × means unavailable capacity; no interior value is copied to a cut end.</p>']
    for i,(case,fig) in enumerate(figures.items()):
        assert tuple(fig.layout.xaxis.range)==(0,20)
        component='Vuy' if name=='Shear' else 'Tu'
        force=next(t for t in fig.data if str(t.name).startswith(component+' '))
        assert list(force.x)==list(range(21))
        html.append(pio.to_html(fig,include_plotlyjs=i==0,full_html=False,config={'displayModeBar':False,'responsive':True}))
        fig.write_json(OUT/(f'actual_source_{name.lower()}_case{i+1}.json'))
        ax=axes.flat[i]
        for trace in fig.data:
            if str(trace.name).startswith('Gov.') or 'lines' not in str(trace.mode or 'lines'):continue
            ax.plot(list(trace.x),[float(y) if y is not None else float('nan') for y in trace.y],
                color=trace.line.color or '#2563eb',linewidth=1.8,
                linestyle={'dash':'--','dot':':','dashdot':'-.'}.get(trace.line.dash or 'solid','-'),
                label=trace.name if trace.showlegend is not False else '_nolegend_')
        for item in (fig.layout.meta or {}).get('unavailable_capacity',[]):
            ax.text(item['x_m'],.03,'×',transform=ax.get_xaxis_transform(),ha='center',color='#64748b',fontsize=13)
        ax.set_xlim(0,20);ax.set_xticks([0,5,10,15,20]);ax.grid(color='#cbd5e1',linewidth=.5)
        ax.spines[['top','right']].set_visible(False);ax.set_title(case.split(' / ',2)[-1],loc='left',fontsize=10)
        ax.set_xlabel('Physical x (m)');ax.set_ylabel('Shear (kN)' if name=='Shear' else 'Torsion (kN-m)')
        ax.legend(loc='upper center',bbox_to_anchor=(.5,-.2),ncol=3,frameon=False,fontsize=8)
    canvas.suptitle(name+' — Final-Composite | actual input | bearing CL x=0.4 / 19.6 m',x=.07,ha='left',fontsize=13)
    canvas.text(.07,.018,'Exact production coordinates. Numerical screening; source/anchorage/interface REVIEW retained. Grey × = unavailable capacity.',fontsize=9,color='#334155')
    canvas.subplots_adjust(left=.07,right=.98,top=.91,bottom=.14,hspace=.65,wspace=.22)
    canvas.savefig(OUT/('actual_source_'+name.lower()+'_full_span.png'));plt.close(canvas)
    html.append('</body></html>');(OUT/('actual_source_'+name.lower()+'_full_span.html')).write_text('\n'.join(html))
summary={'release':'IGIRDER.SHEARCOMP1','status':'PASS','actual_source_model':model.name,
    'native_rows':80,'preserved_components':480,'external_Nu_all_zero':bool(source['Nu'].eq(0).all()),'physical_domain_m':[0,20],
    'bearings':support_basis(state,span_m=20),'direct_calculation_seconds':seconds,'frames':frames,
    'source_and_materials_unchanged':True,'hypothetical_confirmations_added':False,
    'meaning':'QA PASS means calculations/source preservation verified; it does not convert engineering REVIEW/FAIL to PASS.'}
(OUT/'actual_source_verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
