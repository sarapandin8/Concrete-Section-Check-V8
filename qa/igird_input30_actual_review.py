"""Actual supplied files and full-app input workflow verification.

No capacity is inferred. The output project differs only by added, input-only
CSI source tables. The supplied raw Loads and independent dowel unknowns stay
unchanged. This is not a full composite resistance implementation.
"""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import argparse
import hashlib
import json
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.io import csi_component_sources as components
from concrete_pmm_pro.io.project_io import project_from_json, project_to_json, project_from_session_state, apply_project_to_session_state
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui import girder_csi_import as importer
from concrete_pmm_pro.ui.igird_composite_inputs import input_plan
from concrete_pmm_pro.ui.igird_dowel_joint import CACHE_KEY
from concrete_pmm_pro.analysis import igird_dowel_joint as joint

ROOT=Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()


class Upload(BytesIO):
    def __init__(self,path):
        super().__init__(path.read_bytes());self.name=path.name


def run(app):
    app.run(timeout=90)
    assert not app.exception,[item.message for item in app.exception]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--dl',type=Path,required=True)
    parser.add_argument('--u2a',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--full-app',action='store_true')
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    original=json.loads(args.project.read_text());draft=deepcopy(original)
    snapshots=[];checks=[]
    for path,mode,rows in [(args.dl,'static',276),(args.u2a,'unverified',552)]:
        evidence='User identified the supplied DL source as a static load case' if mode=='static' else ''
        source=components.capture(path.read_bytes(),path.name,source_mode=mode,
            concurrency_confirmed=mode=='static',evidence=evidence)
        assert not source['errors'] and len(source['records'])==3*rows
        file=Upload(path)
        frame,errors=importer._native_preview([file],source_mode=mode,
            concurrency_confirmed=mode=='static',evidence=evidence)
        assert not errors and len(frame)==rows and frame.Girder.nunique()==6
        assert not frame.Girder.str.contains('Beam|Slab|Entire',case=False).any()
        snapshots.append(source)
        checks.append({'filename':path.name,'source_sha256':source['sha256'],
            'girder_load_rows':len(frame),'girders':frame.Girder.nunique(),
            'component_input_rows':len(source['records']),'auto_mapping':True,
            'force_source_mode':mode})
    draft['metadata'][components.KEY]=components.collection(snapshots)
    prior=deepcopy(draft);prior['metadata'].pop(components.KEY)
    assert prior==original
    output=args.output_dir/'I_Girder_20m_INPUT30_DRAFT.json'
    output.write_text(json.dumps(draft,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    state={};apply_project_to_session_state(project_from_json(output.read_text()),state)
    config=ap._igird_interface_shear_settings_from_state(state)
    plan=input_plan(config,params=state['section_parameters'],state=state)
    assert len(plan['components'])==12 and plan['design_status']=='REVIEW'
    assert all(row['Complete components'] for row in plan['components'])
    assert {row['Input state'] for row in plan['components']}=={'Single-state source','State pairing required'}
    assert all(zone['x_start_m'] is None and zone['x_end_m'] is None for zone in config['dowel_zones'])
    assert config[joint.KEY]['action_rows']==[]
    pd.DataFrame(plan['reused']).to_csv(args.output_dir/'INPUT30_reused_inputs.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(plan['missing']).to_csv(args.output_dir/'INPUT30_missing_inputs.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(plan['pending']).to_csv(args.output_dir/'INPUT30_pending_model_steps.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(plan['components']).to_csv(args.output_dir/'INPUT30_component_sources.csv',index=False,encoding='utf-8-sig')
    result={'version':'IGIRDER.INPUT30','project_json':output.name,
        'baseline_sha256':hashlib.sha256(args.project.read_bytes()).hexdigest(),
        'project_diff':'Only metadata.csi_component_force_sources added',
        'loads_preserved':digest(draft['loads'])==digest(original['loads']),
        'section_rebar_prestress_dowel_unknowns_preserved':prior==original,
        'actual_source_checks':checks,'component_inventory':plan['components'],
        'missing_inputs':plan['missing'],'pending_model_steps':plan['pending'],'full_composite_Tn_or_VT_implemented':False,
        'engineering_equations_changed':False,'browser_visual_QA':False,
        'browser_visual_QA_reason':'No local browser executable; browser download did not return a usable archive'}
    if args.full_app:
        # Exercise the real importer UI, using the supplied DL bytes and its
        # explicit Import loads action. The user's saved draft is not modified.
        script="""
import streamlit as st
from concrete_pmm_pro.ui.girder_csi_import import render_import
render_import(state_key='beam_uls_loads_table',editor_key='qa_editor',key_prefix='input30qa',force_unit='kN',moment_unit='kN-m')
"""
        files=[Upload(args.dl)]
        def uploader(label,*a,**k):return files if label==importer.UPLOAD_LABEL else None
        with patch('streamlit.file_uploader',side_effect=uploader):
            app=AppTest.from_string(script,default_timeout=90)
            for k,v in state.items():app.session_state[k]=deepcopy(v)
            run(app)
            assert not app.text_input and not app.multiselect
            assert [w.label for w in app.checkbox]==['Advanced import settings']
            chooser=next(r for r in app.radio if r.label=='Force source')
            chooser.set_value('Static case / explicit step');run(app)
            next(b for b in app.button if b.label=='Import loads').click();run(app)
            bank=pd.DataFrame(app.session_state['igird_uls_member_bank'])
            captured=components.saved(app.session_state.filtered_state)
            assert len(bank)==276 and bank.Girder.nunique()==6
            assert len(captured['sources'])==1 and len(captured['sources'][0]['records'])==828
            retained=deepcopy(captured);run(app)
            assert components.saved(app.session_state.filtered_state)==retained
            restored={};apply_project_to_session_state(project_from_json(project_to_json(
                project_from_session_state(app.session_state.filtered_state))),restored)
            assert components.saved(restored)==retained
            result['actual_import_AppTest']={'normal_path_without_member_mapping':True,
                'new_confirmation_checkboxes':0,'girder_load_rows':276,'component_input_rows':828,
                'source_tables_persist_in_project':True,'view_does_not_reimport':True}
        # Run the complete app with the original model and its added input
        # sources. No source import or calculation is triggered on navigation.
        state['_nav_active_workspace']='Analysis';state['_nav_analysis_subpage']='ULS Strength'
        app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=90)
        for k,v in state.items():app.session_state[k]=deepcopy(v)
        with patch.object(ap,'_igird_dowel_joint_review',wraps=ap._igird_dowel_joint_review) as calculate, \
                patch.object(joint,'solve_mechanism',side_effect=AssertionError('Unknown joint forces must not run the mechanism solver')):
            run(app)
            next(r for r in app.radio if r.label=='Flexure stage').set_value('Final — Composite');run(app)
            next(t for t in app.toggle if t.key=='igird_compact_details_Flexure').set_value(True);run(app)
            assert calculate.call_count==0
            assert not any('joint29_actions_' in str(e.key) for e in app.dataframe)
            before=deepcopy(app.session_state.filtered_state.get(ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY,{}))
            next(b for b in app.button if b.label=='Calculate U-dowel Joint').click();run(app)
            assert calculate.call_count==1
            review=app.session_state[CACHE_KEY]['result']
            assert review['missing_actions'] and len(review['requirements'])==3
            assert app.session_state.filtered_state.get(ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY,{})==before
            payload=project_to_json(project_from_session_state(app.session_state.filtered_state))
            assert CACHE_KEY not in payload
            assert digest(json.loads(payload)['loads'])==digest(original['loads'])
            restored={};apply_project_to_session_state(project_from_json(payload),restored)
            assert components.saved(restored)==components.saved(state)
            for workspace in ('Result Summary','Report / QA'):
                app.session_state['_nav_active_workspace']=workspace;run(app)
                assert calculate.call_count==1
            result['full_app_AppTest']={'joint_calculate_calls':calculate.call_count,
                'no_implicit_solver_call':True,'no_manual_joint_force_grid_by_default':True,
                'no_production_ULS_mutation':True,'raw_Loads_unchanged':True,
                'source_inputs_survive_project_roundtrip':True,'solver_results_not_saved':True,
                'summary_report_no_rerun':True}
    (args.output_dir/'INPUT30_actual_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'component_inventory','missing_inputs'}},ensure_ascii=False))


if __name__=='__main__':main()
