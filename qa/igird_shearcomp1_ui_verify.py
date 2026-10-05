"""SHEARCOMP1 native full-span UI verification and independent substitutions.

The two models are controlled QA assumptions: fy=390 MPa, continuous bars,
ld=1000 mm; support-face anchorage is first false, then explicitly selected.
These assumptions do not modify the user's fixture or Excel file.
"""
import copy
import json
import math
import os
import pickle
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

REPO = Path(os.environ.get('CSP_QA_REPO', Path(__file__).resolve().parents[1]))
OUT = Path(os.environ.get('CSP_QA_OUT', REPO/'qa/evidence/igird_shearcomp1'))
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO))
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json

state = {}
model = REPO/'qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json'
apply_project_to_session_state(project_from_json(model.read_text()), state)
from concrete_pmm_pro.analysis.igird_shear_support import SETTINGS_KEY as SUPPORT_KEY, support_basis
state[SUPPORT_KEY] = {'locations_confirmed':True,'offset_reference':'centerline',
    'left_offset_m':.4,'right_offset_m':.4,'left_bearing_length_mm':0.,'right_bearing_length_mm':0.,
    'note':'User offsets; CL interpretation. Width remains unknown.'}
source = state['beam_uls_loads_table'].copy(deep=True)
assert len(source) == 80 and source['Nu'].eq(0).all()
route = ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
started = time.perf_counter()
direct = ap._beam_uls_calculate_selected_check(state,source,selected_check='Shear + Torsion',strength_route=route)
seconds = time.perf_counter()-started
keys = ('shear_check_df','shear_critical_section_df','shear_boundary_capacity_df',
        'torsion_check_df','torsion_boundary_capacity_df','combined_vt_df')
assert direct['shear_critical_section_df'].empty
assert len(direct['shear_check_df']) == 80
pd.testing.assert_frame_equal(source,state['beam_uls_loads_table'],check_exact=True)
diagram = direct['torsion_diagram_capacity_df']
assert len(diagram) == 84 and diagram['φTn kN-m'].notna().sum() == 76
assert diagram['D/C value'].isna().all() and diagram['Status'].eq('DIAGRAM ONLY').all()
below = diagram.loc[diagram['Threshold status'].eq('BELOW THRESHOLD')]
assert len(below) == 17 and below['φTn kN-m'].notna().all()

from concrete_pmm_pro.visualization.igird_uls_chart_display import native_csi_diagram_rows
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import plotly.io as pio

figures = {}; unanchored = {}; anchored = {}; shear_cases = {}; shear_unanchored = {}; calc_times = {}
original = ap._render_beam_uls_browser_plotly_figure
def capture(fig,**kwargs):
    original(fig,**kwargs)
    figures[str(fig.layout.title.text)] = copy.deepcopy(fig)
def pick(title):
    return next(fig for key,fig in figures.items() if key.startswith(title))
def element(items,label):
    return next(item for item in items if item.label==label)
def ok(at):
    assert not at.exception,[e.message for e in at.exception]
def calculate(at,label):
    start = time.perf_counter()
    element(at.button,label).click().run(timeout=90);ok(at)
    calc_times[label] = time.perf_counter()-start
def case_checks(at,name,output,*,full_capacity):
    with (patch.object(ap,'_beam_uls_calculate_selected_check',side_effect=AssertionError('Case review must not solve')),
         patch.object(ap,'_beam_uls_igird_torsion_diagram_capacity_dataframe',side_effect=AssertionError('Case review must not evaluate capacity'))):
        element(at.radio,'Chart view').set_value('Selected case — demand / capacity').run(timeout=30);ok(at)
        before = copy.deepcopy(at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY][name])
        selector = element(at.selectbox,'Case for diagram')
        for case in selector.options:
            element(at.selectbox,'Case for diagram').set_value(case).run(timeout=30);ok(at)
            fig = pick(name+' Check'); output[case] = copy.deepcopy(fig)
            assert tuple(fig.layout.xaxis.range)==(0,20)
            component = 'Vuy' if name=='Shear' else 'Tu'
            trace = next(trace for trace in fig.data if str(trace.name).startswith(component+' '))
            expected = native_csi_diagram_rows(source.loc[source['Case Name'].eq(case)],member_length_m=20,source_context_df=source)
            assert list(trace.x)==list(range(21))==expected['Station x (m)'].tolist()
            assert list(trace.y)==expected[component].tolist()
            if name=='Torsion':
                resistance = next(trace for trace in fig.data if trace.name=='±φTn')
                assert list(resistance.x)==list(range(21))
                assert sum(math.isfinite(value) for value in resistance.y)==(21 if full_capacity else 19)
                missing = (fig.layout.meta or {}).get('unavailable_capacity',[])
                assert ([row['x_m'] for row in missing]==[0,20]) if not full_capacity else not missing
            elif full_capacity:
                resistance = next(trace for trace in fig.data if trace.name=='±φVn')
                assert min(resistance.x)==0 and max(resistance.x)==20
                assert all(math.isfinite(value) for value in resistance.y)
            names = [trace.name for trace in fig.data if trace.showlegend is not False]
            assert len(names)==len(set(names)) and len(names)<=3
            for key in keys:
                if key in before:
                    pd.testing.assert_frame_equal(before[key],at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY][name][key],check_exact=True)

with patch.object(ap,'_render_beam_uls_browser_plotly_figure',side_effect=capture), patch.object(ap,'_render_beam_uls_static_plotly_figure',side_effect=AssertionError('No Analysis rasterization')):
    at = AppTest.from_file(str(REPO/'app.py'))
    for key,value in state.items(): at.session_state[key] = copy.deepcopy(value)
    at.session_state['_nav_active_workspace'] = 'Analysis'
    at.run(timeout=30);ok(at)
    element(at.radio,'ULS check to calculate').set_value('Shear + Torsion').run(timeout=30);ok(at)
    calculate(at,'Calculate Shear + Torsion')
    for name,output in [('Shear',shear_unanchored),('Torsion',unanchored)]:
        element(at.radio,'ULS check to calculate').set_value(name).run(timeout=30);ok(at)
        case_checks(at,name,output,full_capacity=False)
    # Actual bearing controls. The 400-mm bearing width below is a QA
    # assumption, never added to the deliverable user project.
    assert support_basis({SUPPORT_KEY:at.session_state[SUPPORT_KEY]},span_m=20)['status']=='BEARING LENGTH REQUIRED'
    element(at.number_input,'Left bearing length along beam (mm; 0 = unknown)').set_value(400.).run(timeout=30);ok(at)
    element(at.number_input,'Right bearing length along beam (mm; 0 = unknown)').set_value(400.).run(timeout=30);ok(at)
    basis = support_basis({SUPPORT_KEY:at.session_state[SUPPORT_KEY]},span_m=20)
    assert all(math.isclose(s['inside_face_x_m'],expected,abs_tol=1e-12) for s,expected in zip(basis['supports'],[.6,19.4]))
    # Actual bar controls, under an explicitly hypothetical verified QA model.
    element(at.checkbox,'Left physical end x=0: full bar strength is verified').check().run(timeout=30);ok(at)
    element(at.checkbox,'Right physical end x=L: full bar strength is verified').check().run(timeout=30);ok(at)
    calculate(at,'Calculate Torsion')
    case_checks(at,'Torsion',anchored,full_capacity=True)
    full = at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]['Torsion']['torsion_diagram_capacity_df'].copy(deep=True)
    assert len(full)==84 and full['φTn kN-m'].notna().all()
    full.to_csv(OUT/'torsion_diagram_anchored_qa.csv',index=False)
    diagram.to_csv(OUT/'torsion_diagram_unanchored_qa.csv',index=False)
    element(at.radio,'ULS check to calculate').set_value('Shear').run(timeout=30);ok(at)
    calculate(at,'Calculate Shear')
    case_checks(at,'Shear',shear_cases,full_capacity=True)
    shear_diagram = at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]['Shear']['shear_diagram_capacity_df'].copy(deep=True)
    shear_diagram.to_csv(OUT/'shear_diagram_anchored_qa.csv',index=False)
    for step in ['Max','Min']:
        for x in ['0.000 m','20.000 m']:
            rows = shear_diagram.loc[shear_diagram['Case'].str.contains('/ '+step+' /') & shear_diagram['Governing x'].eq(x)]
            assert len(rows)==2 and rows['φVn kN'].nunique()==1
    # Both flexure stages and interface shear use their actual Calculate buttons.
    element(at.radio,'ULS check to calculate').set_value('Flexure').run(timeout=30);ok(at)
    element(at.radio,'Flexure stage').set_value('Construction — Noncomposite').run(timeout=30);ok(at)
    calculate(at,'Calculate Construction Flexure')
    construction = next(fig for title,fig in figures.items() if 'Construction noncomposite' in title)
    assert tuple(construction.layout.xaxis.range)==(0,20)
    element(at.radio,'Flexure stage').set_value('Final — Composite').run(timeout=30);ok(at)
    calculate(at,'Calculate Final Composite Flexure')
    final = next(fig for title,fig in figures.items() if 'Final composite +M' in title)
    demands = [trace for trace in final.data if str(trace.name).startswith('Mux ')]
    assert len(demands)==4 and all(list(trace.x)==list(range(21)) for trace in demands)
    element(at.checkbox,'Girder stirrups extend across the interface and are fully developed/anchored in the CIP deck').check().run(timeout=30);ok(at)
    calculate(at,'Calculate Interface Shear')
    interface = pick('Girder–Deck Interface Shear')
    assert tuple(interface.layout.xaxis.range)==(0,20)
    element(at.radio,'ULS check to calculate').set_value('Shear + Torsion').run(timeout=30);ok(at)
    calculate(at,'Calculate Shear + Torsion')
    final_entry=at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]['Shear + Torsion']
    for key in keys:
        if isinstance(final_entry.get(key),pd.DataFrame): final_entry[key].to_csv(OUT/(key+'.csv'),index=False)
    assert len(final_entry['shear_critical_section_df'])==8
    assert not ap._beam_uls_shear_near_support_load_indices(final_entry['shear_check_df'])
    eligible=ap._beam_uls_shear_design_rows_for_governing(final_entry['shear_check_df'])
    assert eligible.loc[eligible['Station type'].eq('LOAD STATION')].shape[0]==80
    for key in ('shear_check_df','torsion_check_df','combined_vt_df'):
        frame=final_entry[key]
        assert frame.loc[frame['Composite action status'].notna(),'Composite action status'].isin(['REVIEW','NOT APPLICABLE','FAIL','-']).all()  # Be remains explicitly unverified.
    combined = pick('Combined Shear + Torsion Utilization')
    assert tuple(combined.layout.xaxis.range)==(0,20)
    # Navigation is read-only, including the newly stored capacity diagram.
    with patch.object(ap,'_beam_uls_calculate_selected_check',side_effect=AssertionError('Review must not solve')):
        at.run(timeout=30);ok(at)
    pd.testing.assert_frame_equal(source,at.session_state['beam_uls_loads_table'],check_exact=True)

def export_panels(case_figures,stem,subtitle):
    canvas,axes = plt.subplots(2,2,figsize=(15,9),dpi=130,sharex=True)
    html = ['<!doctype html><html><head><meta charset="utf-8"><title>'+stem+'</title></head><body><h2>'+subtitle+'</h2>']
    for i,(case,fig) in enumerate(case_figures.items()):
        ax = axes.flat[i]
        fig.write_json(OUT/(stem+'_'+str(i+1)+'.json'))
        html.append(pio.to_html(fig,include_plotlyjs=i==0,full_html=False,config={'displayModeBar':False,'responsive':True}))
        for trace in fig.data:
            if str(trace.name).startswith('Gov.'): continue
            mode = str(trace.mode or 'lines')
            if 'lines' not in mode: continue
            x = [float(v) for v in trace.x]; y = [float(v) if v is not None else float('nan') for v in trace.y]
            label = trace.name if trace.showlegend is not False else '_nolegend_'
            ax.plot(x,y,color=trace.line.color or '#1f77b4',
                linestyle={'dash':'--','dot':':','dashdot':'-.'}.get(trace.line.dash or 'solid','-'),
                linewidth=2.1,marker='o' if 'markers' in mode else None,markersize=2.3,label=label)
        for annotation in fig.layout.annotations:
            if annotation.yref=='paper' and annotation.text=='×':
                ax.text(float(annotation.x),float(annotation.y),'×',transform=ax.get_xaxis_transform(),
                    ha='center',va='bottom',color='#64748b',fontsize=14)
        ax.set_xlim(0,20);ax.set_xticks([0,5,10,15,20])
        ax.set_xlabel('x (m)');ax.set_ylabel('Torsion (kN-m)' if stem.startswith('torsion') else 'Shear (kN)')
        ax.set_title(case.split(' / ',2)[-1],loc='left',fontsize=11)
        ax.grid(color='#cbd5e1',linewidth=.5);ax.spines[['top','right']].set_visible(False)
        ax.legend(loc='upper center',bbox_to_anchor=(.5,-.2),ncol=3,frameon=False,fontsize=9)
    canvas.suptitle(subtitle,fontsize=14,ha='left',x=.065)
    canvas.text(.065,.017,'Exact production force/resistance coordinates. Shared endpoints retain their original Excel row. QA assumptions do not change the source files.',fontsize=9,color='#334155')
    canvas.subplots_adjust(left=.065,right=.98,top=.91,bottom=.13,hspace=.7,wspace=.22)
    canvas.savefig(OUT/(stem+'.png'));plt.close(canvas)
    html.append('</body></html>');(OUT/(stem+'.html')).write_text('\n'.join(html))

export_panels(anchored,'torsion_all_cases_full_span','Torsion: all 4 CSI row sets, x=0–20 m | QA: verified bar properties and both end anchors')
export_panels(unanchored,'torsion_all_cases_unanchored','Torsion: all 4 CSI row sets | QA: unanchored ends; grey × = unavailable end resistance')
export_panels(shear_cases,'shear_all_cases_full_span','Shear: all 4 CSI row sets, x=0–20 m | QA: verified bar properties and both end anchors')

# Independent US-unit checks for every diagram station, including below-threshold rows and physical endpoints.
comparisons = 0
for _,row in full.iterrows():
    theta = 29+3500*max(0,min(.006,row['εs raw']))
    kip=4448.2216152605;inch=25.4;ksi=6.894757293168
    tn_kip_in=2*(row['Ao mm2']/inch**2)*(row['At/s mm2/mm']/inch)*(row['fy MPa']/ksi)/math.tan(math.radians(theta))
    expected = row['φ']*tn_kip_in*kip*inch/1e6
    assert math.isclose(row['φTn kN-m'],expected,rel_tol=2e-9,abs_tol=1e-8)
    assert math.isclose(row['θ deg'],theta,rel_tol=2e-9,abs_tol=1e-8)
    comparisons += 2
shear_comparisons=0
for _,row in shear_diagram.iterrows():
    eps=max(0,min(.006,row['εs raw']));beta=4.8/(1+750*eps);theta=29+3500*eps
    fc=row["f'c MPa"]/ksi;bw=row['bw mm']/inch;dv=row['dv mm']/inch;cot=1/math.tan(math.radians(theta))
    vc=.0316*beta*math.sqrt(fc)*bw*dv*kip/1000
    vs=(row['Av/s mm2/m']/1000/inch)*(row['fy MPa']/ksi)*dv*cot*kip/1000
    limit=.25*fc*bw*dv*kip/1000
    assert math.isclose(row['φVn kN'],row['φ']*min(vc+vs,limit),rel_tol=2e-9,abs_tol=1e-8)
    assert math.isclose(row['θ deg'],theta,rel_tol=2e-9,abs_tol=1e-8)
    shear_comparisons+=2
result = {'release':'IGIRDER.SHEARCOMP1','status':'PASS','method':'Actual app.py Streamlit Calculate and case/anchorage controls; independent US-unit torsion equation check',
    'streamlit_exceptions':0,'native_rows':80,'preserved_force_components':480,
    'source_frames_unchanged':True,'direct_combined_calculation_seconds':seconds,
    'actual_ui_calculation_seconds':calc_times,'force_diagrams_tested':16,'full_case_force_domain':[0,20],
    'torsion_diagram_stations':84,'unanchored_numeric_resistance_stations':76,'anchored_numeric_resistance_stations':84,
    'below_threshold_resistance_stations_restored':17,'independent_torsion_scalars_checked':comparisons,
    'shear_shared_endpoints_use_actual_forces':True,'shear_diagram_stations':84,'independent_shear_diagram_scalars_checked':shear_comparisons,
    'both_flexure_stages_interface_and_combined_ui':'PASS','review_solver_calls':0,
    'source_fixture_and_workbook_modified':False,'automatic_anchorage_confirmation':False,'automatic_material_definition':False,'bearing_offsets_m':[.4,.4],
    'unknown_bearing_length_creates_no_critical_marker':True,'bearing_width_400mm_for_ui_QA_only':True,
    'all_original_shear_rows_retained':True,'effective_width_not_auto_confirmed':True,
    'preview_method':'Scientific plots and standalone HTML from production Plotly figures; no browser screenshot claim'}
(OUT/'shearcomp1_ui_result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)
