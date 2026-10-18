"""Verify the CSI source-torque policy against an actual input-only project.

python qa/validate_csitu46_project.py --project FILE.json --output DIRECTORY
Software verification only; no full-composite structural design acceptance.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import logging
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
for name in ('streamlit','streamlit.runtime.scriptrunner_utils.script_run_context'):
    logging.getLogger(name).setLevel(logging.ERROR)
import pandas as pd
from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state
from concrete_pmm_pro.io.girder_csi_import import source_info
from concrete_pmm_pro.io import csi_force_reference as ref
from concrete_pmm_pro.ui import analysis_page as ap, csi_reference_analysis as adapter
from concrete_pmm_pro.ui import igird_station_section as station, igird_composite_steel45 as model


def near(a,b):
    assert math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-8),(a,b)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    raw=args.project.read_bytes(); project=json.loads(raw); state={}
    apply_project_to_session_state(project_from_json(raw.decode()),state)
    original=deepcopy(state['section_parameters'])
    interface=deepcopy(state['beam_girder_interface_shear_settings'])
    bank=project['metadata']['workflow_load_tables']['igird_uls_member_bank']
    rows=pd.DataFrame(bank).copy(deep=True)
    for field in ('Station x (m)','Nu','Vuy','Vux','Tu','Muy','Mux'):
        rows[field]=pd.to_numeric(rows[field],errors='raise')
    route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
    conversions=0
    for _,row in rows.iterrows():
        local=station.at_station(state,float(row['Station x (m)']))
        for check in ('Torsion','Shear + Torsion'):
            moved=adapter.convert_for_check(local,row,check_name=check)
            near(moved['Tu'],row['Tu'])
            for field in ('Nu','Vuy','Vux'): near(moved[field],row[field])
            trace=ref.trace_columns(moved)
            assert trace['T shift applied'] is False
            near(trace['T reference y mm'],trace['CSI C y mm'])
            conversions+=1
    u2a=rows.loc[rows.apply(lambda r:(source_info(r) or {}).get('case')=='U2A',axis=1)]
    review=model.calculate(state,u2a,route=route)
    for r in review['rows']:
        assert 'calculation' in r,r
        physical=u2a.loc[u2a['Girder'].eq(r['Girder']) & u2a['Station x (m)'].between(0.,20.,inclusive='neither')]
        near(abs(r['source_CSI']['Tu']),pd.to_numeric(physical['Tu']).abs().max())
        near(r['actions']['tu_Nmm']/1e6,r['source_CSI']['Tu'])
        assert r['calculation']['accepted_Tn_kNm'] is None
    focus=u2a.loc[u2a['Station x (m)'].sub(18.).abs()<1e-8]
    focus_review=model.calculate(state,focus,route=route)
    examples=[]
    for r in focus_review['rows']:
        chosen=focus.loc[focus['Girder'].eq(r['Girder']) & focus.apply(
            lambda row:(source_info(row) or {}).get('row')==r['Source Excel row'],axis=1)].iloc[[0]]
        source=chosen.iloc[0]
        direct=ap._beam_uls_torsion_result_for_row(state,source,strength_route=route)
        combined=ap._beam_uls_combined_vt_check_dataframe(state,chosen,strength_route=route).iloc[0].to_dict()
        near(direct['Demand kN-m'],source['Tu'])
        near(combined['Tu kN-m'],source['Tu'])
        for check in ('Torsion','Shear + Torsion'):
            isolated=deepcopy(state)
            result=ap._beam_uls_calculate_selected_check(isolated,chosen,selected_check=check,strength_route=route)
            key='torsion_check_df' if check=='Torsion' else 'combined_vt_df'
            frame=result[key]
            for _,saved in frame.iterrows():
                near(saved['Demand kN-m'] if check=='Torsion' else saved['Tu kN-m'],source['Tu'])
                assert saved['T shift applied'] is False
            signature=ap._beam_uls_check_input_hash(isolated,chosen,strength_route=route,check_name=check)
            clean=ap._beam_uls_store_manual_result(isolated,check,input_hash=signature,result=result)
            assert model.KEY not in clean and model.current(isolated,signature) is not None
        examples.append({'girder':r['Girder'],'station_m':18.,'case':'U2A',
            'source_excel_row':r['Source Excel row'],'CSI_Tu_kNm':float(source['Tu']),
            'torsion_Tu_used_kNm':direct['Demand kN-m'],'VT_Tu_used_kNm':combined['Tu kN-m'],
            'Tn_transverse_screen_kNm':direct.get('Tn kN-m'),
            'torsion_DC_screen':direct.get('D/C value'),
            'VT_DC_screen':combined.get('Overall D/C value'),
            'status':combined.get('Overall status',combined.get('Status')),
            'reference':ref.trace_columns(adapter.convert_for_check(state,source,check_name='Shear + Torsion')),
            'model_Tn_review_kNm':r['calculation']['model_Tn_kNm'],
            'model_VT_DC_review':r['calculation']['model_VT_DC']})
    assert state['section_parameters']==original
    assert state['beam_girder_interface_shear_settings']==interface
    assert args.project.read_bytes()==raw
    audit={'version':ref.SOURCE_TORSION_POLICY,'source_file':args.project.name,
        'source_sha256':hashlib.sha256(raw).hexdigest(),'source_rows':len(rows),
        'adapter_conversions_verified':conversions,'source_file_unchanged':True,
        'scope':'CSI scalar torque retained. I-hoop and two-path capacities remain screening/review, not validated full-composite resistance.',
        'other_actions':'P/V2/V3 unchanged; M2/M3 retain the existing bending transport. No torsion redistribution or capacity multiplier.',
        'examples':examples,'maximum_reported_torque_model_selection':review,
        'focus_station_review':focus_review,'verification_status':'PASS'}
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'csitu46_project_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    for r in examples: print({k:v for k,v in r.items() if k!='reference'},flush=True)
    print('PASS:',conversions,'conversions from',len(rows),'native source rows; source file unchanged',flush=True)


if __name__=='__main__': main()
