"""Replay the accepted Project 31 data without publishing research resistance.

The source bank has 640 imported rows. Each member review selects one real
section; this is not a full-span 640-section capacity calculation.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import streamlit

from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state
from concrete_pmm_pro.ui import analysis_page as ap,igird_station36 as station,igird_joint37 as joint,igird_member_results as mr


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output-project',type=Path,required=True);parser.add_argument('--evidence-dir',type=Path,required=True)
    args=parser.parse_args();args.evidence_dir.mkdir(parents=True,exist_ok=True)
    raw=json.loads(args.baseline.read_text());proposed=deepcopy(raw)
    proposed['metadata'][joint.KEY]={'enabled':True}
    encoded=json.dumps(proposed,ensure_ascii=False,indent=2,allow_nan=False)
    args.output_project.parent.mkdir(parents=True,exist_ok=True);args.output_project.write_text(encoded)
    expected=deepcopy(raw);expected['metadata'][joint.KEY]={'enabled':True};assert expected==proposed
    state={};apply_project_to_session_state(project_from_json(encoded),state)
    before=deepcopy(state['igird_uls_member_bank']);initial=deepcopy(state)
    route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
    witnesses={};summary=[]
    for name,frame in mr.member_inputs(state).items():
        source=station.calculate(state,frame,route=route)
        assert source['status']=='MODEL REVIEW ONLY',source.get('reason')
        with patch.object(joint.solver,'limit',side_effect=AssertionError('Intersecting job geometry must not invoke a capacity LP')) as lp, \
             patch.object(joint.solver,'compatible_state',side_effect=AssertionError('Intersecting job geometry must not invoke a compatibility QP')) as qp:
            result=joint.calculate(state,frame,route=route,station=source)
        assert lp.call_count==qp.call_count==0
        assert result['status']=='INPUT GEOMETRY REVIEW',result.get('reason')
        assert result['accepted_phiTn_Nmm'] is result['accepted_VT_factor'] is result['full_composite_Tn_Nmm'] is None
        assert result['source']==source['source'] and result['source_actions']==source['source_actions']
        assert result['transported_actions']==source['transported_actions']
        geometry=result['geometry_audit'];assert len(geometry['U_intersections'])==23
        assert geometry['A_bend_minimum_mm']==84 and geometry['A_web_cover_maximum_mm']==108
        assert geometry['A_necessary_feasible_intervals_mm']==[] and geometry['no_silent_relocation']
        assert result['compatibility']['ready'] is False
        assert all(r['model_T_limit_Nmm'] is r['model_VT_factor'] is None and not r['ready'] for r in result['tests'].values())
        # Plotting is also read-only and uses the same geometry ledger.
        figure=joint.figure(source,result)
        assert len(next(t for t in figure.data if t.name=='Input path clashes').x)==23
        assert next(t for t in figure.data if t.name=='Continuous U-dowel')
        witnesses[name]=result
        summary.append({'member':name,'source_rows':len(frame),'selected':result['source'],
            'source_actions':result['source_actions'],'transported_actions':result['transported_actions'],
            'U_input_intersections':len(geometry['U_intersections']),
            'derived_hoop_intersections':len(geometry['derived_hoop_intersections']),
            'A_necessary_range_mm':[84,108],'A_remaining_intervals_mm':[],
            'capacity_LP_calls':lp.call_count,'compatibility_QP_calls':qp.call_count,
            'accepted_phiTn_Nmm':None,'accepted_VT_factor':None,'full_composite_Tn_Nmm':None})
    pd.testing.assert_frame_equal(pd.DataFrame(before),pd.DataFrame(state['igird_uls_member_bank']))
    # Research execution may not modify any in-memory input, including Pe.
    assert json.dumps(initial,sort_keys=True,default=str)==json.dumps(state,sort_keys=True,default=str)
    restored={};apply_project_to_session_state(project_from_json(args.output_project.read_text()),restored)
    pd.testing.assert_frame_equal(pd.DataFrame(before),pd.DataFrame(restored['igird_uls_member_bank']))
    assert joint.settings(restored)=={'enabled':True}
    (args.evidence_dir/'joint_witnesses.json').write_text(json.dumps(witnesses,ensure_ascii=False,indent=2,allow_nan=False))
    record={'status':'PASS — SOFTWARE / INPUT GEOMETRY REVIEW ONLY',
        'baseline_sha256':hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        'project_sha256':hashlib.sha256(args.output_project.read_bytes()).hexdigest(),
        'raw_load_bank_sha256':hashlib.sha256(json.dumps(before,sort_keys=True,default=str).encode()).hexdigest(),
        'raw_loads_unchanged':True,'all_inputs_unchanged_during_review':True,
        'only_serialized_change':'metadata.igird_joint37_settings = {enabled: true}',
        'members':summary,'scope':'Two selected real sections from the 640-row bank. No production composite resistance or structural validation.'}
    (args.evidence_dir/'project_replay.json').write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps({'status':record['status'],'rows':sum(r['source_rows'] for r in summary),'members':summary},ensure_ascii=False))


if __name__=='__main__':main()
