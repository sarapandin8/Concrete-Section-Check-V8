"""Reproduce the STEEL45 example from a supplied I-girder project JSON.

Run in the repository: python qa/validate_steel45_project.py --project FILE
--output DIRECTORY [--station 18]. This validates software and source handling,
not the structural constitutive model or project design acceptance.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
for name in ('streamlit','streamlit.runtime.scriptrunner_utils.script_run_context'):
    logging.getLogger(name).setLevel(logging.ERROR)
import pandas as pd
from concrete_pmm_pro.io.project_io import (project_from_json,apply_project_to_session_state,
    project_from_session_state,project_to_json)
from concrete_pmm_pro.io.girder_csi_import import source_info
from concrete_pmm_pro.ui import analysis_page as ap,igird_composite_steel45 as ui


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--station',type=float)
    args=parser.parse_args()
    raw=args.project.read_bytes(); project=json.loads(raw); state={}
    apply_project_to_session_state(project_from_json(raw.decode()),state)
    original_parameters=deepcopy(state['section_parameters'])
    original_interface=deepcopy(state['beam_girder_interface_shear_settings'])
    source=pd.DataFrame(project['metadata']['workflow_load_tables']['igird_uls_member_bank'])
    source=source.loc[source.apply(lambda r:(source_info(r) or {}).get('case')=='U2A',axis=1)]
    if args.station is not None:
        source=source.loc[pd.to_numeric(source['Station x (m)']).sub(args.station).abs()<1e-8]
    # Match Loads' typed analysis frame; raw snapshots in Note stay untouched.
    source=source.copy(deep=True)
    for field in ('Station x (m)','Nu','Vuy','Vux','Tu','Muy','Mux'):
        source[field]=pd.to_numeric(source[field],errors='raise')
    route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
    review=ui.calculate(state,source,route=route)
    assert review['rows'] and all('calculation' in r for r in review['rows'])
    checks=[]
    for item in review['rows']:
        c=item['calculation']; no_u=item['without_U']; no_slab=item['without_slab_longitudinal']
        for key in ('model_Vn_kN','model_Tn_kNm'):
            assert c[key]>=no_u[key]-1e-7
            assert c[key]>=no_slab[key]-1e-7
        for command in ('V','T','VT'):
            witness=c[command]
            assert witness['ready']
            assert max(witness['checks'].values())<2e-7
            assert witness['accepted_Vn_kN'] is None and witness['accepted_Tn_kNm'] is None
        s=c['supplies']
        for witness in [c['V'],c['T'],c['VT']]:
            assert max(witness['U_force_each_N_per_mm'])<=s['u_leg_N_per_mm']+1e-6
        assert item['slab_longitudinal_area_mm2']>0 and item['slab_longitudinal_force_N']>0
        assert item['continuity_flags_preserved']=={'top':False,'bottom':False}
        chosen=source.loc[source.apply(lambda r:(source_info(r) or {}).get('row')==item['Source Excel row'] and
            str(r.get('Girder'))==item['Girder'],axis=1)].iloc[[0]]
        # Exercise all three existing Calculate paths, then verify that review
        # data is detached before the production cache/summary can read it.
        for command in ('Shear','Torsion','Shear + Torsion'):
            local=deepcopy(state)
            returned=ap._beam_uls_calculate_selected_check(local,chosen,selected_check=command,strength_route=route)
            assert ui.KEY in returned and returned[ui.KEY]['rows']
            signature=ap._beam_uls_check_input_hash(local,chosen,check_name=command,strength_route=route)
            stored=ap._beam_uls_store_manual_result(local,command,input_hash=signature,result=returned)
            assert ui.KEY not in stored
            assert ui.current(local,signature) is not None and ui.current(local,'obsolete') is None
            exported=project_to_json(project_from_session_state(local))
            assert ui.RUNTIME_KEY not in exported and ui.KEY not in exported
        checks.append(item['Girder']+': all three Calculate routes, physical supply bounds, current-only review cache and input-only JSON verified')
    assert state['section_parameters']==original_parameters
    assert state['beam_girder_interface_shear_settings']==original_interface
    assert args.project.read_bytes()==raw
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'steel45_project_results.json').write_text(json.dumps(review,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    verification={'status':'PASS','source_file':args.project.name,'source_sha256':hashlib.sha256(raw).hexdigest(),
        'scope':'Software/source integration only; no structural design certification','checks':checks}
    (args.output/'steel45_project_verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n')
    for r in review['rows']:
        print(r['Girder'],r['x (m)'],{k:r['calculation'][k] for k in ('model_Vn_kN','model_Tn_kNm','model_VT_DC')})
    print('Integration verification PASS:',len(checks),'members')


if __name__=='__main__':main()
