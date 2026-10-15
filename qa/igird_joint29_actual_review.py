"""Prepare the unknown-input draft and verify the actual application flow.

Analytical probes are explicitly hypothetical; none are written to the project
or a production result cache. No interface torque is inferred from Girder Tu.
"""
from copy import deepcopy
import argparse
import hashlib
import json
import math
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.analysis import igird_dowel_joint as joint
from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state, project_from_session_state, project_to_json
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.igird_dowel_joint import CACHE_KEY

ROOT=Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--full-app',action='store_true')
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    original=json.loads(args.project.read_text());draft=deepcopy(original)
    key=ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY
    previous=original['metadata'][key]
    cfg={**previous,joint.KEY:{'mode':joint.MODE,'coating':'unknown','anchorage_region':'unknown',
        **{name:None for name in joint.DIMENSIONS},
        'cover_required_mm':original['section_parameters'].get('deck_long_rebar_top_cover_mm'),
        'action_rows':[],
        'drawing_reference':{'projection_above_girder_mm':250.,'horizontal_dimension_mm':220.,
            'note':'Drawing references only; no inference of leg spacing, straight tail or verified development dimensions.'}}}
    draft['metadata'][key]=cfg
    unchanged=deepcopy(draft);unchanged['metadata'][key]=previous
    assert unchanged==original
    path=args.output_dir/'I_Girder_20m_JOINT29_DRAFT.json'
    path.write_text(json.dumps(draft,ensure_ascii=False,indent=2,allow_nan=False))
    state={};apply_project_to_session_state(project_from_json(path.read_text()),state)
    assert ap._igird_interface_shear_settings_from_state(state)==cfg
    before=digest(original['loads'])
    review=ap._igird_dowel_joint_review(state,cfg,code_label='AASHTO LRFD 2020')
    assert review['missing_actions'] and not review['rows'] and len(review['requirements'])==3
    assert all('Coating is unknown' in row['Reason'] for row in review['requirements'])
    requirements=pd.DataFrame(review['requirements'])
    assert requirements['Slab ldh uncoated mm'].sub(190.80277454783032).abs().max()<1e-8
    assert requirements['Girder ld uncoated mm'].sub(637.6631885238107).abs().max()<1e-8
    requirements.to_csv(args.output_dir/'JOINT29_actual_anchorage_requirements.csv',index=False,encoding='utf-8-sig')
    pending=deepcopy(cfg)
    pending[joint.KEY]['action_rows']=[{'Case':'QA pending source — not a design load',
        'Station x (m)':10.45714,'qx_kN_per_m':None,'qy_kN_per_m':None,'n_kN_per_m':None,
        'mx_kNm_per_m':None,'Source':None}]
    unresolved=ap._igird_dowel_joint_review(state,pending,code_label='AASHTO LRFD 2020')
    assert all(r['Status']=='REVIEW' for r in unresolved['rows'])
    assert not any(t['result']['mechanism'] for t in unresolved['traces'])
    assert joint.KEY in project_to_json(project_from_session_state(state))
    assert before==digest(original['loads'])
    result={'version':joint.VERSION,'project_json':path.name,'original_project_sha256':hashlib.sha256(args.project.read_bytes()).hexdigest(),
        'all_other_project_inputs_unchanged':True,'loads_unchanged':True,'dowel_extents_inferred':False,
        'interface_actions_inferred_from_girder':False,'drawing_dimensions_used_as_verified_inputs':False,
        'actual_anchorage_alternatives':review['requirements'],'pending_actual_row_status':[r['Status'] for r in unresolved['rows']],
        'pending_actual_row_has_no_mechanism_solution':True,'browser_screenshots_verified':False}
    avf=2*math.pi*12**2/4*1000/150
    steel=.90*avf*390/1000
    probes=[]
    for label,n,s,expected in [('pure shear',0.,100.,steel/100),
                             ('pure opening',100.,0.,steel/100),
                             ('opening plus shear',100.,100.,steel/200)]:
        solved=joint.solve_mechanism(width_mm=600,leg_spacing_mm=200,avf_mm2_per_m=avf,
            fy_MPa=390,fc_weaker_MPa=35,surface_key='roughened_girder_slab',
            qx_kN_per_m=s,qy_kN_per_m=0,n_kN_per_m=n,mx_kNm_per_m=0)
        assert solved['ready'] and abs(solved['capacity_factor']-expected)<1e-8
        probes.append({'Scope':'HYPOTHETICAL EQUATION QA — NOT PROJECT CAPACITY','Case':label,
            'n_kN_per_m':n,'qx_kN_per_m':s,'capacity_factor':solved['capacity_factor'],
            'closed_form_factor':expected,'equilibrium_residual':solved['equilibrium_residual']})
    pd.DataFrame(probes).to_csv(args.output_dir/'JOINT29_hypothetical_equation_checks.csv',index=False,encoding='utf-8-sig')
    result['hypothetical_equation_checks']=probes
    exact_m=(steel*600/2-steel**2/(2*(.70*.85*35)))/1000
    mesh=[]
    for cells in (32,64,128):
        solved=joint.solve_mechanism(width_mm=600,leg_spacing_mm=200,avf_mm2_per_m=avf,
            fy_MPa=390,fc_weaker_MPa=35,surface_key='roughened_girder_slab',
            qx_kN_per_m=0,qy_kN_per_m=0,n_kN_per_m=0,mx_kNm_per_m=100,cells=cells)
        mesh.append({'cells':cells,'moment_limit_kNm_per_m':100*solved['capacity_factor']})
    assert mesh[0]['moment_limit_kNm_per_m']<=mesh[1]['moment_limit_kNm_per_m']<=mesh[2]['moment_limit_kNm_per_m']<=exact_m+1e-8
    result['hypothetical_roll_mesh_check']={'continuous_pressure_block_limit_kNm_per_m':exact_m,'meshes':mesh}
    # Exercise the production station/polygon adapter with deliberately
    # hypothetical complete joint inputs. Never apply these to the saved model.
    verified_probe=deepcopy(cfg)
    verified_probe['dowel_zones']=[{'Zone':'HYPOTHETICAL QA ONLY','x_start_m':0.,'x_end_m':20.,
        'Diameter_mm':12.,'Legs':2,'Spacing_mm':150.,'fy_MPa':390.}]
    verified_probe[joint.KEY].update(coating='uncoated',anchorage_region='interior',row_spacing_mm=80.,
        slab_ldh_available_mm=250.,hook_tail_mm=180.,hook_inside_bend_mm=72.,girder_ld_available_mm=900.,
        action_rows=[{'Case':'HYPOTHETICAL JOINT QA ONLY','Station x (m)':10.45714,
            'qx_kN_per_m':100.,'qy_kN_per_m':0.,'n_kN_per_m':100.,'mx_kNm_per_m':0.,
            'Source':'Synthetic equation/pipeline test — not project demand'}])
    probe=ap._igird_dowel_joint_review(state,verified_probe,code_label='AASHTO LRFD 2020')
    assert probe['rows'][0]['Anchorage']=='DIMENSION CHECKS MET'
    assert abs(probe['rows'][0]['Capacity factor']-steel/200)<1e-8
    assert probe['rows'][0]['Status']=='REVIEW'
    assert json.loads(path.read_text())==draft
    result['hypothetical_actual_geometry_pipeline']={'scope':'Synthetic inputs only; no project or production result write',
        'status':probe['rows'][0]['Status'],'capacity_factor':probe['rows'][0]['Capacity factor'],
        'bonded_leg_path_check':probe['traces'][0]['result']['anchorage']['checks']['bonded_leg_concrete_cover'],
        'draft_file_unchanged_after_probe':True}
    if args.full_app:
        state['_nav_active_workspace']='Analysis';state['_nav_analysis_subpage']='ULS Strength'
        app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60)
        for name,value in state.items():app.session_state[name]=deepcopy(value)
        def run():
            app.run(timeout=60)
            assert not app.exception,[e.message for e in app.exception]
        with patch.object(ap,'_igird_dowel_joint_review',wraps=ap._igird_dowel_joint_review) as calculate, \
                patch.object(joint,'solve_mechanism',side_effect=AssertionError('Unknown real joint actions must not run the mechanism solver')):
            run()
            for radio in app.radio:
                if radio.label=='Flexure stage':radio.set_value('Final — Composite');break
            run()
            for toggle in app.toggle:
                if toggle.key=='igird_compact_details_Flexure':toggle.set_value(True);break
            run()
            assert calculate.call_count==0
            controls={button.label:button for button in app.button}
            assert 'Calculate U-dowel Joint' in controls, list(controls)
            prod_before=deepcopy(app.session_state.filtered_state.get(ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY,{}))
            controls['Calculate U-dowel Joint'].click();run()
            assert calculate.call_count==1
            saved=app.session_state[CACHE_KEY]['result']
            assert saved['missing_actions'] and len(saved['requirements'])==3
            assert app.session_state.filtered_state.get(ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY,{})==prod_before
            payload=project_to_json(project_from_session_state(app.session_state.filtered_state))
            assert CACHE_KEY not in payload
            restored=json.loads(payload)
            assert digest(restored['loads'])==before
            for workspace in ('Result Summary','Report / QA'):
                app.session_state['_nav_active_workspace']=workspace;run()
                assert calculate.call_count==1
            result['full_app_apptest']={'calculate_calls':calculate.call_count,'no_automatic_mechanism_solve':True,
                'no_production_uls_result_mutation':True,'no_persistent_solver_witness':True,
                'loads_preserved_after_ui_project_roundtrip':True,'summary_report_no_rerun':True}
    (args.output_dir/'JOINT29_actual_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
