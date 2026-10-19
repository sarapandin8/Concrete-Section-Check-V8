"""Real app Calculate -> visible code figures, without an LP result cache.

Four original CSI vectors exercise both girders and Max/Min / below-threshold
states. Full 640-vector replay and real browser rendering are separate checks.
"""
import argparse
from copy import deepcopy
import hashlib,json,logging,math
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
for name in ('streamlit','streamlit.runtime.scriptrunner_utils.script_run_context'):
    logging.getLogger(name).setLevel(logging.ERROR)
logging.getLogger('streamlit.deprecation_util').disabled=True
import pandas as pd
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY,activate_member
from concrete_pmm_pro.io.girder_csi_import import source_info
from concrete_pmm_pro.ui import analysis_page as ap,igird_composite_steel45 as research,igird_member_results as members
from concrete_pmm_pro.ui import igird_code52_workspace as compact


def ok(app):assert not app.exception,[e.message for e in app.exception]


def production_snapshot(app):
    caches=[app.session_state[members.CACHE_KEY],app.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]]
    def stable(value):
        if isinstance(value,pd.DataFrame):return value.to_json(orient='split',double_precision=15)
        if isinstance(value,dict):return {k:stable(v) for k,v in value.items()}
        if isinstance(value,(tuple,list)):return [stable(v) for v in value]
        return str(value)
    return json.dumps(stable(caches),sort_keys=True,ensure_ascii=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
    raw=a.project.read_bytes();state={};apply_project_to_session_state(project_from_json(raw.decode()),state)
    params=deepcopy(state['section_parameters']);interface=deepcopy(state['beam_girder_interface_shear_settings'])
    bank=pd.DataFrame(state[BANK_KEY])
    sample=bank.loc[bank.apply(lambda row:(source_info(row) or {}).get('row') in {491,556,167,237}
        and (source_info(row) or {}).get('case')=='U2A',axis=1)].copy()
    assert len(sample)==4
    state[BANK_KEY]=sample;state['beam_uls_loads_table']=sample.iloc[[0]].copy()
    activate_member(state,str(sample.iloc[0]['Girder']))
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=180)
    for k,v in state.items():app.session_state[k]=deepcopy(v)
    app.session_state['_nav_active_workspace']='Analysis'
    app.session_state['_nav_analysis_subpage']='ULS Strength'
    records=[]
    with patch.object(research,'calculate',wraps=research.calculate,side_effect=AssertionError('Code UI must not solve LP')) as lp,\
         patch.object(research,'payload',side_effect=AssertionError('Code UI must not request LP')),\
         patch.object(ap,'_beam_uls_calculate_selected_check',wraps=ap._beam_uls_calculate_selected_check) as calc,\
         patch.object(ap,'_render_beam_uls_browser_plotly_figure',wraps=ap._render_beam_uls_browser_plotly_figure) as renderer:
        app.run();ok(app)
        for check in ('Shear','Torsion','Shear + Torsion'):
            if check=='Shear + Torsion':
                # Remove previous standalone results: the combined action
                # must itself create both subchecks for every imported member.
                old=deepcopy(app.session_state[members.CACHE_KEY])
                for entry in old.values():
                    entry.pop('Shear',None);entry.pop('Torsion',None)
                app.session_state[members.CACHE_KEY]=old
                manual=dict(app.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY])
                manual.pop('Shear',None);manual.pop('Torsion',None)
                app.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]=manual
            next(w for w in app.radio if w.label=='ULS check to calculate').set_value(check).run();ok(app)
            before=calc.call_count;render_before=renderer.call_count
            next(w for w in app.button if w.label.startswith('Calculate '+check+' — all')).click().run();ok(app)
            assert calc.call_count-before==2
            figures=[c.args[0] for c in renderer.call_args_list[render_before:]
                if (c.args[0].layout.meta or {}).get('igird_maxmin_check')==check]
            assert len(figures)==2
            initial_members={(f.layout.meta or {}).get('igird_maxmin_member') for f in figures}
            assert len(initial_members)==1
            for fig in figures:
                assert tuple(fig.layout.xaxis.range)==(0.,20.)
                assert any(t.y is not None and any(isinstance(y,(int,float)) and math.isfinite(y) for y in t.y)
                    for t in fig.data)
            assert not any('Model Tn · U + slab (kN-m)' in table.value.columns for table in app.dataframe)
            assert not any(w.label=='Reference summary — I-girder hoop / code route' for w in app.expander)
            panels=[w for w in app.expander if w.label in {
                compact.DETAIL_LABEL,compact.AUDIT_LABEL,compact.STUDY_LABEL}]
            assert len(panels)==3 and not any(w.proto.expanded for w in panels)
            assert not any(w.label.startswith('Girder: ') for w in app.expander)
            after=calc.call_count
            other=next(n for n in sample['Girder'].unique() if n not in initial_members)
            render_before=renderer.call_count
            next(w for w in app.selectbox if w.label=='Girder to review').set_value(other).run();ok(app)
            assert calc.call_count==after
            changed_figures=[c.args[0] for c in renderer.call_args_list[render_before:]]
            assert changed_figures and all((f.layout.meta or {}).get('igird_maxmin_member')==other for f in changed_figures)
            next(w for w in app.selectbox if w.label=='Load case to review').set_value('All load cases').run();ok(app)
            assert calc.call_count==after
            next(w for w in app.selectbox if w.label=='Load case to review').set_value(compact.AUTO_CASE).run();ok(app)
            assert calc.call_count==after
            cache=app.session_state[members.CACHE_KEY]
            for member in cache:
                result=cache[member][check]['result']
                assert research.KEY not in result
                frame=result[{'Shear':'shear_check_df','Torsion':'torsion_check_df','Shear + Torsion':'combined_vt_df'}[check]]
                assert not frame.empty
                if 'T shift applied' in frame:
                    assert not frame.loc[frame['T shift applied'].notna(),'T shift applied'].astype(bool).any()
                if check=='Shear + Torsion':
                    for sub in ('Shear','Torsion'):
                        assert cache[member][sub]['input_hash']==members.result_hash(
                            app.session_state.filtered_state,members.member_inputs(
                                app.session_state.filtered_state)[member],check_name=sub,
                            route=ap._beam_uls_strength_route_from_state(
                                app.session_state.filtered_state,is_bridge=True,is_building=False))
                        pd.testing.assert_frame_equal(cache[member][sub]['result'][compact.FRAME_KEYS[sub]],
                            result[compact.FRAME_KEYS[sub]])
            after=calc.call_count;app.run();ok(app);assert calc.call_count==after
            records.append({'check':check,'code_calculation_calls':after-before,
                'real_code_figures':len(figures),'girders_with_figures':2,'span_m':[0,20],
                'default_visible_girder':True,'details_and_study_collapsed':True,
                'member_case_redraw_calculation_calls':0,'LP_calls':lp.call_count})
            print('PASS actual app:',check,len(figures),'code figures, no LP',flush=True)
        after=calc.call_count
        for sub in ('Shear','Torsion','Shear + Torsion'):
            next(w for w in app.radio if w.label=='ULS check to calculate').set_value(sub).run();ok(app)
            assert calc.call_count==after
            summaries=[t.value for t in app.dataframe if 'Result state' in t.value]
            assert summaries and summaries[0]['Result state'].eq('CURRENT').all()
        after=calc.call_count
        for workspace in ('Result Summary','Report / QA'):
            app.session_state['_nav_active_workspace']=workspace;app.run();ok(app)
            assert calc.call_count==after and lp.call_count==0
        app.session_state['_nav_active_workspace']='Analysis'
        changed=dict(app.session_state['section_parameters']);changed['Tslab_mm']+=1.
        app.session_state['section_parameters']=changed;app.run();ok(app)
        assert calc.call_count==after
        # The stale engineering inputs must not resurrect a previous graph.
        current=[table.value for table in app.dataframe if 'Result state' in table.value.columns]
        assert current and all(current[0]['Result state'].eq('STALE'))
        app.session_state['section_parameters']=deepcopy(params);app.run();ok(app)
        assert calc.call_count==after and lp.call_count==0
        # Only the explicit optional action may run the real research engine.
        snapshot=production_snapshot(app)
        study_member=renderer.call_args.args[0].layout.meta['igird_maxmin_member']
        lp.side_effect=None
        next(w for w in app.button if w.label=='Run case study — selected girder').click().run();ok(app)
        assert lp.call_count==1 and calc.call_count==after
        assert production_snapshot(app)==snapshot
        selected_rows=lp.call_args.args[1]
        pd.testing.assert_frame_equal(selected_rows,members.member_inputs(app.session_state.filtered_state)[study_member])
        assert len(selected_rows)==2
        assert compact.study_fingerprint(app.session_state.filtered_state,selected_rows,
            member=study_member,route=ap._beam_uls_strength_route_from_state(
                app.session_state.filtered_state,is_bridge=True,is_building=False)) in app.session_state[research.RUNTIME_KEY]
        app.run();ok(app);assert lp.call_count==1 and calc.call_count==after
        changed=dict(app.session_state['section_parameters']);changed['Tslab_mm']+=1.
        app.session_state['section_parameters']=changed;app.run();ok(app)
        assert any('No case study for the current inputs' in message.value for message in app.info)
        assert lp.call_count==1 and calc.call_count==after
        app.session_state['section_parameters']=deepcopy(params);app.run();ok(app)
        assert lp.call_count==1 and calc.call_count==after
        for workspace in ('Result Summary','Report / QA'):
            app.session_state['_nav_active_workspace']=workspace;app.run();ok(app)
            assert calc.call_count==after and lp.call_count==1
        assert app.session_state['section_parameters']==params
        assert app.session_state['beam_girder_interface_shear_settings']==interface
    # The same compact workspace must also work with no imported member bank.
    single=deepcopy(state);single[BANK_KEY]=[]
    single['beam_uls_loads_table']=sample.loc[sample['Girder'].eq(sample.iloc[0]['Girder'])].copy()
    one=AppTest.from_file(str(ROOT/'app.py'),default_timeout=180)
    for k,v in single.items():one.session_state[k]=deepcopy(v)
    one.session_state['_nav_active_workspace']='Analysis';one.session_state['_nav_analysis_subpage']='ULS Strength'
    with patch.object(research,'calculate',side_effect=AssertionError('No automatic LP')),\
         patch.object(ap,'_beam_uls_calculate_selected_check',wraps=ap._beam_uls_calculate_selected_check) as calc:
        one.run();ok(one)
        for check in ('Shear','Torsion','Shear + Torsion'):
            next(w for w in one.radio if w.label=='ULS check to calculate').set_value(check).run();ok(one)
            before=calc.call_count
            next(w for w in one.button if w.label=='Calculate '+check).click().run();ok(one)
            assert calc.call_count==before+1
            assert any(w.label=='Girder to review' for w in one.selectbox)
            assert any(w.label==compact.STUDY_LABEL and not w.proto.expanded for w in one.expander)
        print('PASS single-member code workspace, all 3 checks',flush=True)
    assert a.project.read_bytes()==raw
    record={'status':'PASS','release':'IGIRDER.CODE52','source_sha256':hashlib.sha256(raw).hexdigest(),
        'fixture_original_rows':4,'full_bank_replay':'Separate evidence','Calculate':records,
        'Summary_Report_calculation_calls':0,'stale_input_hides_old_results_without_solving':True,
        'original_inputs_preserved':True,'automatic_LP_calls':0,'explicit_case_study_calls':1,
        'case_study_selected_member_only':True,'case_study_production_cache_unchanged':True,
        'combined_calculation_populates_all_three_code_views':True,
        'single_member_all_three_checks':'PASS',
        'structural_design_acceptance':False}
    a.output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print('PASS current/stale/read-only workflow',flush=True)


if __name__=='__main__':main()
