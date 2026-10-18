"""Replay the actual JSON bank through FULLVT48; software verification only.

Run explicitly from the command line. No benchmark solver runs on UI navigation.
The original source vectors and drawing inputs are never edited.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import logging
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
for name in ('streamlit','streamlit.runtime.scriptrunner_utils.script_run_context'):
    logging.getLogger(name).setLevel(logging.ERROR)
import pandas as pd
from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state
from concrete_pmm_pro.ui import analysis_page as ap,igird_composite_steel45 as model


def clean(value):
    if isinstance(value,dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)): return [clean(v) for v in value]
    if hasattr(value,'item'): return clean(value.item())
    if isinstance(value,float) and not math.isfinite(value): return None
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    raw=args.project.read_bytes();project=json.loads(raw);state={}
    apply_project_to_session_state(project_from_json(raw.decode()),state)
    params=deepcopy(state['section_parameters'])
    interface=deepcopy(state['beam_girder_interface_shear_settings'])
    bank=pd.DataFrame(project['metadata']['workflow_load_tables']['igird_uls_member_bank'])
    original=bank.copy(deep=True)
    route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
    snapshots=[];started=time.monotonic()
    for name,rows in bank.groupby('Girder',sort=False):
        print('Calculating every source vector:',name,len(rows),flush=True)
        saved=model.calculate(state,rows.copy(deep=True),route=route)
        assert len(saved['station_rows'])+len(saved['excluded_rows'])==len(rows)
        for record in saved['station_rows']:
            assert record['Status']=='MODEL REVIEW',record
            assert record['Tu shift applied'] is False,record
            assert math.isclose(record['Actions used']['tu_Nmm']/1e6,record['CSI actions']['Tu'],rel_tol=1e-12,abs_tol=1e-9)
            assert record['Maximum numerical residual']<2e-7,record
        for item in saved['rows']+saved['governing_rows']:
            for key in ('accepted_Vn_kN','accepted_Tn_kNm','accepted_VT_factor'):
                assert item['calculation'][key] is None
        snapshots.append(saved)
        print(json.dumps({'coverage':saved['coverage'],'VT_governors':[
            {**{k:e.get(k) for k in ('Girder','x (m)','Case','Source StepType','Source location type','Source Excel row')},
                'model_Vn_kN':e['calculation']['model_Vn_kN'],'model_Tn_kNm':e['calculation']['model_Tn_kNm'],
                'nominal_VT_DC':e['calculation']['model_VT_DC']} for e in saved['rows']],
            'elapsed_seconds':round(time.monotonic()-started,2)},ensure_ascii=False),flush=True)
        (args.output/'fullvt48_scan_checkpoint.json').write_text(json.dumps(clean(snapshots),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    assert args.project.read_bytes()==raw
    assert state['section_parameters']==params and state['beam_girder_interface_shear_settings']==interface
    pd.testing.assert_frame_equal(bank,original)
    rows=[r for s in snapshots for r in s['station_rows']]
    summary={'release':'IGIRDER-FULLVT48','status':'PASS','verification_scope':'Software replay, not structural validation',
        'source_sha256':hashlib.sha256(raw).hexdigest(),'raw_rows':len(bank),'interior_rows':len(rows),
        'physical_end_rows_excluded':sum(len(s['excluded_rows']) for s in snapshots),
        'numeric_rows':sum(r['Status']=='MODEL REVIEW' for r in rows),
        'below_threshold_numeric_rows':sum(r['Baseline torsion threshold']=='BELOW THRESHOLD' for r in rows),
        'rows_exceeding_nominal_VT':sum(r['Model nominal V–T D/C'] is not None and r['Model nominal V–T D/C']>1+1e-9 for r in rows),
        'max_numerical_residual':max(r['Maximum numerical residual'] for r in rows),
        'source_T_preserved_every_row':True,'original_inputs_unchanged':True,
        'runtime_seconds':time.monotonic()-started,'member_results':[
            {'coverage':s['coverage'],'VT_governor':s['rows'][0],
             'source_case_counts':dict(Counter(r['Case'] for r in s['station_rows']))} for s in snapshots]}
    (args.output/'fullvt48_project_replay.json').write_text(json.dumps(clean(summary),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='member_results'},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
