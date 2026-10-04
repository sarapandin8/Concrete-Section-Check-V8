"""Actual app controls, source preservation and exact production chart previews.
All P=0/material/development additions are hypothetical, in-memory QA only.
"""
import copy, json, math, os, sys
from pathlib import Path
from unittest.mock import patch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import plotly.io as pio
from streamlit.testing.v1 import AppTest

REPO=Path(os.environ.get('CSP_QA_REPO',Path(__file__).resolve().parents[1]))
OUT=Path(os.environ.get('CSP_QA_OUT',REPO/'qa/evidence/igird_vtqa1'))
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(REPO))
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.igird_combined_vt import source_readiness_dataframe
from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state,project_from_session_state,project_to_json
from concrete_pmm_pro.io.girder_csi_import import read_tables,prepare_csi_table

def element(elements,label): return next(e for e in elements if e.label==label)
def ok(at): assert not at.exception,[e.message for e in at.exception]
def preview(fig,stem,note):
    fig.write_json(OUT/(stem+'.json'))
    pio.write_html(fig,OUT/(stem+'.html'),include_plotlyjs=True,full_html=True,config={'displayModeBar':False,'responsive':True})
    canvas,ax=plt.subplots(figsize=(13.8,5.4),dpi=120)
    for t in fig.data:
        x=[float(v) for v in t.x]; y=[float(v) if v is not None else float('nan') for v in t.y]
        color=t.line.color or t.marker.color or '#0f172a'
        label=t.name if t.showlegend is not False else '_nolegend_'
        mode=str(t.mode or 'lines')
        if 'lines' in mode:
            ax.plot(x,y,color=color,linestyle={'dash':'--','dot':':','dashdot':'-.'}.get(t.line.dash or 'solid','-'),
                linewidth=2.3,marker='o' if 'markers' in mode else None,markersize=3,label=label)
        elif 'markers' in mode: ax.scatter(x,y,color=color,marker='D',s=40,label=label,zorder=8)
        if 'text' in mode and t.text:
            for xp,yp,txt in zip(x,y,t.text):
                if math.isfinite(yp): ax.annotate(str(txt),(xp,yp),xytext=(-12 if xp>15 else 8,9),textcoords='offset points',ha='right' if xp>15 else 'left',fontsize=8)
    handles,labels=ax.get_legend_handles_labels()
    assert len(labels)==len(set(labels))
    ax.legend(handles,labels,ncol=min(4,len(labels)),loc='upper center',bbox_to_anchor=(.5,-.17),frameon=False,fontsize=9)
    ax.set_xlim(*fig.layout.xaxis.range)
    if fig.layout.yaxis.range: ax.set_ylim(*fig.layout.yaxis.range)
    ax.set_ylabel(fig.layout.yaxis.title.text,fontsize=10)
    ax.set_xlabel('Distance from left end of member (m)',fontsize=10)
    title=fig.layout.title.text.split('<br>')[0]
    ax.set_title(title+'\nAASHTO LRFD 9th Edition | Left Exterior Girder | P=0 QA',loc='left',fontsize=13,pad=13)
    ax.grid(color='#cbd5e1',linewidth=.5); ax.spines[['top','right']].set_visible(False)
    canvas.text(.065,.025,note,fontsize=8,color='#334155')
    canvas.subplots_adjust(left=.07,right=.98,top=.82,bottom=.28)
    canvas.savefig(OUT/(stem+'.png')); plt.close(canvas)

state={}
fixture=REPO/'qa/fixtures/I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck250.json'
apply_project_to_session_state(project_from_json(fixture.read_text()),state)
workbook=REPO/'qa/fixtures/CSiBridge_Left_Exterior_Max_Min_latest.xlsx'
raw=read_tables(workbook.read_bytes(),workbook.name)['Left Exterior Girder'].copy(deep=True)
raw.loc[raw.index[1:],'P']=0.0
source=prepare_csi_table(raw,sheet_name='Left Exterior Girder').frame
state['beam_uls_loads_table']=source.copy(deep=True)
for row in state['beam_girder_torsion_zone_settings']:
    row.update({'Use for Torsion':True,'Closed Loop':True,'135° Hook':True})
state['beam_girder_torsion_settings'].update(corner_longitudinal_reinforcement_confirmed=True,longitudinal_perimeter_distribution_confirmed=True)
bar_source=[b.model_dump() for b in state['rebars']]
figures={}; original=ap._render_beam_uls_browser_plotly_figure

def capture(fig,**kw):
    original(fig,**kw); figures[str(fig.layout.title.text)]=copy.deepcopy(fig)
def pick(title): return next(fig for key,fig in figures.items() if key.startswith(title))
def calculate(at):
    element(at.button,'Calculate Shear + Torsion').click().run(timeout=60); ok(at)
    return at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]['Shear + Torsion']['combined_vt_df'].copy(deep=True)

with patch.object(ap,'_render_beam_uls_browser_plotly_figure',side_effect=capture),patch.object(ap,'_render_beam_uls_static_plotly_figure',side_effect=AssertionError('No Analysis rasterization')):
    at=AppTest.from_file(str(REPO/'app.py'))
    for key,value in state.items(): at.session_state[key]=copy.deepcopy(value)
    at.session_state['_nav_active_workspace']='Analysis'
    at.run(timeout=30); ok(at)
    element(at.radio,'ULS check to calculate').set_value('Shear + Torsion').run(timeout=30);ok(at)
    assert element(at.button,'Define SD40').disabled
    before=calculate(at)
    assert before['Overall D/C value'].isna().all()
    assert before['Calculation status'].eq('PARTIAL').any()
    assert before['Transverse D/C value'].notna().any()
    assert before.loc[before['Status'].eq('FAIL'),'Failure reason'].str.len().gt(0).all()
    assert source_readiness_dataframe(before)['Required source / review'].str.contains('SD40').any()
    assert any('Longitudinal material missing: SD40' in w.value for w in at.warning)
    assert all(check in at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY] for check in ['Shear','Torsion','Shear + Torsion'])
    before.to_csv(OUT/'screenshot_cage_only_combined.csv',index=False)
    preview(pick('Shear + Torsion — utilization'),'combined_cage_only_overview','Original JSON + photographed hoop confirmations. Longitudinal material/development missing: partial checks only.')
    # Actual inline material control; nothing is inferred from the grade name.
    element(at.number_input,'Verified fy for SD40 (MPa)').set_value(390.0).run(timeout=30);ok(at)
    element(at.button,'Define SD40').click().run(timeout=30);ok(at)
    assert [m.name for m in at.session_state['rebar_materials']]==['SD40']
    defined=calculate(at)
    defined.to_csv(OUT/'material_defined_unconfirmed_development.csv',index=False)
    # Actual development UI controls. QA assumption: continuous straight bars,
    # ld=1000 mm, no full-strength support-face anchorage.
    element(at.checkbox,'All active ordinary bars are continuous over the full physical member').check().run(timeout=30);ok(at)
    element(at.number_input,'Verified governing straight-bar development length ld (mm)').set_value(1000.0).run(timeout=30);ok(at)
    complete=calculate(at)
    assert complete['Calculation status'].eq('COMPLETE').any()
    assert not complete['Status'].eq('PASS').any(), 'Native envelopes do not prove concurrent actions'
    complete.to_csv(OUT/'combined_vt_df.csv',index=False)
    preview(pick('Shear + Torsion — utilization'),'combined_overview','QA: SD40 fy=390 MPa, continuous bars, ld=1000 mm, unanchored ends. Native envelope acceptance remains REVIEW/FAIL.')
    final_frames={}
    for name,key in [('Shear','shear_check_df'),('Torsion','torsion_check_df')]:
        with patch.object(ap,'_beam_uls_calculate_selected_check',side_effect=AssertionError('Review must not solve')):
            element(at.radio,'ULS check to calculate').set_value(name).run(timeout=30);ok(at)
            fig=pick(name+' — utilization')
            assert [t.name for t in fig.data if t.showlegend is not False]==['Max D/C','Limit = 1.0']
            assert tuple(fig.layout.xaxis.range)==(0,20)
            preview(fig,name.lower()+'_overview','Maximum original case/check D/C; one limit line. Source gaps remain gaps. In-memory verified-input QA only.')
            frame=at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY][name][key].copy(deep=True)
            frame.to_csv(OUT/(key+'.csv'),index=False); final_frames[key]=frame
            element(at.radio,'Chart view').set_value('Selected case — demand / capacity').run(timeout=30);ok(at)
            case=element(at.selectbox,'Case for diagram').value
            detail=pick(name+' Check')
            names=[t.name for t in detail.data if t.showlegend is not False]
            assert len(names)==len(set(names)) and len(names)<=3,names
            component='Vuy' if name=='Shear' else 'Tu'
            trace=next(t for t in detail.data if t.name.startswith(component+' ') or t.name.startswith('Demand '+component))
            expected=source.loc[source['Case Name'].eq(case)].sort_values('Station x (m)',kind='stable')
            assert list(trace.x)==expected['Station x (m)'].tolist()
            assert list(trace.y)==expected[component].tolist()
            assert '±φVn' in names if name=='Shear' else '±φTn' in names
            assert tuple(detail.layout.xaxis.range)==(0,20)
            preview(detail,name.lower()+'_selected_case','One original signed CSI case; its own positive/negative resistance. End-zone missing stiffness is not patched or extrapolated.')
            # Switching display options never changes cached engineering rows.
            pd.testing.assert_frame_equal(frame,at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY][name][key])
    pd.testing.assert_frame_equal(source,at.session_state['beam_uls_loads_table'])
    assert [b.model_dump() for b in at.session_state['rebars']]==bar_source
    saved=project_to_json(project_from_session_state(at.session_state._state.filtered_state))
    restored={};apply_project_to_session_state(project_from_json(saved),restored)
    assert restored['rebar_materials'][0].fy_MPa==390
    assert restored['igird_longitudinal_development_settings']['development_length_mm']==1000
    assert not restored['igird_longitudinal_development_settings']['left_end_anchored_confirmed']
    assert not restored['igird_longitudinal_development_settings']['right_end_anchored_confirmed']
    (OUT/'hypothetical_verified_input_qa.json').write_text(saved)
result={'method':'Full app.py Streamlit AppTest, actual Calculate and material/development controls',
    'streamlit_exceptions':0,'native_rows':len(source),'numeric_source_components_preserved':len(source)*6,
    'missing_material_not_auto_defined':True,'photographed_transverse_confirmations_respected':True,
    'partial_before_rows':int(before['Calculation status'].eq('PARTIAL').sum()),
    'partial_before_transverse_numeric_rows':int(before['Transverse D/C value'].notna().sum()),
    'overall_before_numeric_rows':int(before['Overall D/C value'].notna().sum()),
    'verified_qa_overall_numeric_rows':int(complete['Overall D/C value'].notna().sum()),
    'combined_rows':len(complete),'shear_rows':len(final_frames['shear_check_df']),'torsion_rows':len(final_frames['torsion_check_df']),
    'default_legend_entries':2,'selected_case_legend_entries_at_most':3,'full_span':[0,20],
    'force_coordinates_unchanged':True,'review_solver_calls':0,'analysis_rasterization_calls':0,
    'native_envelope_coupled_pass_withheld':True,'original_bar_geometry_unchanged':True,
    'material_and_development_json_roundtrip':'PASS','user_fixture_and_workbook_modified':False,
    'preview_rendering':'Matplotlib from exact production Plotly coordinates; standalone HTML embeds JS',
    'browser_visual_verification':'Not performed; these scientific previews are not browser screenshots'}
(OUT/'vtqa1_ui_result.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2),flush=True)
