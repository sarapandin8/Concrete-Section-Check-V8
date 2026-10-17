"""Prepare the authorized proposal and replay every imported member's station.

No runtime numerical result is written to Project JSON. The separate witness
file is QA evidence of the idealization, not structural validation.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pandas as pd
import streamlit

from concrete_pmm_pro.analysis.igird_station36_recommendations import propose
from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state
from concrete_pmm_pro.ui import analysis_page as ap,igird_station36 as ui,igird_member_results as mr


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output-project',type=Path,required=True);parser.add_argument('--evidence-dir',type=Path,required=True)
    args=parser.parse_args();args.evidence_dir.mkdir(parents=True,exist_ok=True)
    raw=json.loads(args.baseline.read_text());state={}
    apply_project_to_session_state(project_from_json(args.baseline.read_text()),state)
    before=deepcopy(state['igird_uls_member_bank'])
    interface,rows,ledger=propose(ap._igird_interface_shear_settings_from_state(state),state['section_parameters'],
        state['girder_strand_layout_table'].to_dict('records'),dowel_db_mm=12.,dowel_fy_MPa=390.,
        mesh_proposal={'Diameter_mm':12.,'Spacing_mm':150.})
    # Preserve unrelated serialized fields exactly, including optional nulls.
    proposed=deepcopy(raw);meta=proposed['metadata']
    meta.update({ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY:interface,'girder_strand_layout_table':rows,
        ui.KEY:{'enabled':True},ui.RECOMMENDATIONS:ledger})
    encoded=json.dumps(proposed,ensure_ascii=False,indent=2,allow_nan=False)
    args.output_project.parent.mkdir(parents=True,exist_ok=True);args.output_project.write_text(encoded)
    restored={};apply_project_to_session_state(project_from_json(encoded),restored)
    pd.testing.assert_frame_equal(pd.DataFrame(before),pd.DataFrame(restored['igird_uls_member_bank']))
    # All changes must lie inside the four authorized metadata fields.
    expected=deepcopy(raw)
    for key in (ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY,'girder_strand_layout_table',ui.KEY,ui.RECOMMENDATIONS):
        expected['metadata'][key]=proposed['metadata'][key]
    assert expected==proposed
    assert len(ledger['changes'])==13
    source_json=json.dumps(before,sort_keys=True,default=str)
    route=ap._beam_uls_strength_route_from_state(restored,is_bridge=True,is_building=False)
    results={};summary=[]
    for name,frame in mr.member_inputs(restored).items():
        result=ui.calculate(restored,frame,route=route);results[name]=result
        assert result['status']=='MODEL REVIEW ONLY',result.get('reason')
        assert result['accepted_phiTn_Nmm'] is result['accepted_VT_factor'] is result['full_composite_Tn_Nmm'] is None
        assert result['u_dowel_anchorage']['status']=='DIMENSION CHECKS MET'
        assert len(result['longitudinal_inventory'])==64 # 34 actual bars + 30 individual strands
        for key in ('pure_torsion_without_prestress','pure_torsion','actual_five_actions'):
            model=result[key];assert model['ready']
            for check in ('equilibrium_relative','resource_relative','bounds_relative','duality_relative','global_relative'):
                assert model[check]<1e-7,(name,key,check)
            assert all(b['embedded'] for b in model['trace']['longitudinal_ledger'])
        summary.append({'member':name,'source_rows':len(frame),'selected':result['source'],
            'source_actions':result['source_actions'],'transported_actions':result['transported_actions'],
            'pure_T_core_model_kNm':result['pure_torsion']['model_T_limit_Nmm']/1e6,
            'pure_T_core_without_prestress_kNm':result['pure_torsion_without_prestress']['model_T_limit_Nmm']/1e6,
            'actual_five_held_core_T_model_kNm':result['actual_five_actions']['model_T_limit_Nmm']/1e6})
    pd.testing.assert_frame_equal(pd.DataFrame(before),pd.DataFrame(restored['igird_uls_member_bank']))
    (args.evidence_dir/'station_witnesses.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False))
    record={'status':'PASS — SOFTWARE / IDEALIZATION ONLY','baseline_sha256':hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        'project_sha256':hashlib.sha256(args.output_project.read_bytes()).hexdigest(),
        'raw_load_bank_sha256':hashlib.sha256(source_json.encode()).hexdigest(),'raw_loads_unchanged':True,
        'proposed_input_changes':ledger['changes'],'members':summary,'scope':'No production composite Tn / V–T accepted; no structural validation claimed.'}
    (args.evidence_dir/'project_replay.json').write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps({'status':record['status'],'rows':sum(r['source_rows'] for r in summary),'members':len(summary),'proposals':len(ledger['changes'])}))


if __name__=='__main__':main()
