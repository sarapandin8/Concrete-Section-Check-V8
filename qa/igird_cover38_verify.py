"""Replay physical mat coordinates on the accepted Project 31 lineage.

Only slab input fields shown in the user's Flexural(1).pdf (page 3) are
adopted. Other current unsaved UI changes cannot be reconstructed from a PDF.
No solver result is embedded in Project JSON.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import streamlit

from concrete_pmm_pro.analysis import igird_slab_layers as layers
from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state
from concrete_pmm_pro.ui import analysis_page as ap,igird_station36 as station,igird_joint37 as joint,igird_member_results as mr


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output-project',type=Path,required=True);parser.add_argument('--evidence-dir',type=Path,required=True)
    args=parser.parse_args();args.evidence_dir.mkdir(parents=True,exist_ok=True)
    raw=json.loads(args.baseline.read_text());out=deepcopy(raw);cfg=out['metadata'][layers.INTERFACE_KEY]['dowel_connection']
    cfg[layers.ORDER_KEY]=layers.RULE
    cfg['layer_order_previous_longitudinal_covers_mm']={face:raw['section_parameters'][f'deck_long_rebar_{face}_cover_mm'] for face in ('top','bottom')}
    cfg['slab_transverse_mesh']={face:{'Diameter_mm':16.,'Spacing_mm':150.,'Clear_cover_mm':40.,'fy_MPa':390.} for face in ('top','bottom')}
    resolved=layers.resolve(out['section_parameters'],cfg);assert resolved['ready']
    out['section_parameters']=resolved['parameters']
    out['metadata']['igird_cover38_input_provenance']={'source':'User Flexural(1).pdf page 3: transverse top/bottom DB16@150, cover40, fy390. User request: longitudinal bars inside.',
        'basis':'Touching crossed bars; longitudinal cover calculated, not an as-built declaration.',
        'baseline_project_sha256':hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        'scope':'Only slab mesh / layer-order inputs changed. Other values remain from the saved JOINT37 Project 31, not reconstructed from the current unsaved session.'}
    unchanged=deepcopy(out);unchanged['section_parameters']=raw['section_parameters']
    unchanged['metadata'][layers.INTERFACE_KEY]['dowel_connection']=raw['metadata'][layers.INTERFACE_KEY]['dowel_connection']
    unchanged['metadata'].pop('igird_cover38_input_provenance');assert unchanged==raw
    encoded=json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)
    args.output_project.parent.mkdir(parents=True,exist_ok=True);args.output_project.write_text(encoded)
    state={};apply_project_to_session_state(project_from_json(encoded),state)
    before=deepcopy(state['igird_uls_member_bank']);route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
    records=[];witnesses={}
    for name,frame in mr.member_inputs(state).items():
        core=station.calculate(state,frame,route=route);assert core['status']=='MODEL REVIEW ONLY',core.get('reason')
        with patch.object(joint.solver,'limit',side_effect=AssertionError('Known intersecting U input paths must not be solved')) as lp, \
             patch.object(joint.solver,'compatible_state',side_effect=AssertionError('Known intersecting U input paths must not be solved')) as qp:
            result=joint.calculate(state,frame,route=route,station=core)
        assert result['status']=='INPUT GEOMETRY REVIEW',result.get('reason')
        assert result['accepted_phiTn_Nmm'] is result['accepted_VT_factor'] is result['full_composite_Tn_Nmm'] is None
        assert len(result['geometry_audit']['U_intersections'])==23
        layout=layers.resolve(state['section_parameters'],layers.detail_from_state(state))
        assert [r['Auto longitudinal cover (mm)'] for r in layout['rows']]==[56.,56.]
        slab=core['slab_longitudinal_inventory'];assert len(slab)==2
        assert [r['y_mm'] for r in slab]==[1036.,814.]
        assert [r['y'] for r in result['trace']['slab_transverse_layers']]==[1052.,798.]
        witnesses[name]={'slab_layer_geometry':layout,'joint':result}
        records.append({'member':name,'source_rows':len(frame),'selected':result['source'],
            'longitudinal_centres_y_mm':[r['y_mm'] for r in slab],
            'transverse_centres_y_mm':[r['y'] for r in result['trace']['slab_transverse_layers']],
            'source_actions':result['source_actions'],'transported_actions':result['transported_actions'],
            'U_input_intersections':23,'new_LP_calls':lp.call_count,'new_QP_calls':qp.call_count,'production_composite_resistance':'WITHHELD'})
    pd.testing.assert_frame_equal(pd.DataFrame(before),pd.DataFrame(state['igird_uls_member_bank']))
    again={};apply_project_to_session_state(project_from_json(args.output_project.read_text()),again)
    assert again['section_parameters']==state['section_parameters']
    report={'status':'PASS — INPUT / SOFTWARE VERIFICATION ONLY','rows_preserved':len(before),'members':records,
        'layer_rule':layers.RULE,'transverse_input':cfg['slab_transverse_mesh'],'longitudinal_cover_mm':[56,56],
        'project_sha256':hashlib.sha256(args.output_project.read_bytes()).hexdigest(),
        'scope':'Two selected sections from a 640-row bank. Slab ordering corrected; existing U/girder input clashes and full composite structural validation remain unresolved.'}
    (args.evidence_dir/'project_replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
    (args.evidence_dir/'geometry_witnesses.json').write_text(json.dumps(witnesses,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps({'status':report['status'],'rows':len(before),'longitudinal_cover_mm':[56,56],'members':len(records)}))


if __name__=='__main__':main()
