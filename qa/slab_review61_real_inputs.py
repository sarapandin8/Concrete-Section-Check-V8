"""Reproduce the read-only study from unchanged Project JSON and CSI exports."""
from __future__ import annotations
import argparse,json,hashlib
from io import BytesIO
from pathlib import Path
import sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from concrete_pmm_pro.analysis import slab_shell56 as engine,slab_review61 as review
from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state
from concrete_pmm_pro.io.slab_shell_import import parse_files,BANK_KEY,PENDING_KEY


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True)
    p.add_argument('--exports',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    state={};apply_project_to_session_state(project_from_json(a.project.read_text(encoding='utf-8')),state);uploads=[]
    for path in a.exports:
        f=BytesIO(path.read_bytes());f.name=path.name;uploads.append(f)
    package=parse_files(uploads);state[BANK_KEY]=package;state[PENDING_KEY]=package.signature
    nominal=engine.calculate(state);before=nominal['rows'].copy(deep=True);s=review.calculate(nominal)
    pd.testing.assert_frame_equal(before,nominal['rows']);pd.testing.assert_frame_equal(before,s['source'][before.columns])
    keep=s['source'].loc[s['source'][review.STUDY_INCLUDED]];z=s['zone_rows'];keys=review.step_columns(z)+['Zone']
    actual=keep.copy()
    for action in review.ACTIONS:actual[action]*=actual[review.WEIGHT]
    total=actual.groupby(keys,dropna=False)[review.ACTIONS].sum().sort_index()
    means=z.loc[z['Design included']].set_index(keys);rebuilt=means[review.ACTIONS].mul(means['Retained sample area (m²)'],axis=0).sort_index()
    np.testing.assert_allclose(total,rebuilt,rtol=1e-12,atol=1e-9)
    def records(f):return json.loads(f.to_json(orient='records',force_ascii=False))
    governors={}
    for label,column in [('N–M','N–M field D/C'),('Shear','Shear D/C')]:
        valid=keep.loc[keep[column].notna()];governors[label]=records(valid.loc[[valid[column].idxmax()],['AreaElem','Joint','OutputCase','StepType','X (m)','Y (m)',column]])[0]
    result={'version':review.VERSION,'source_rows':nominal['source_rows'],'nominal_rows':nominal['design_rows'],
        'nominal_excluded_rows':nominal['excluded_rows'],'peak_excluded_records':s['excluded_records'],
        'peak_excluded_nodes':s['excluded_nodes'],'peak_excluded_node_cases':s['excluded_node_cases'],
        'retained_study_records':s['retained_records'],'zones':len(s['zone_layout']),'zone_case_records':len(z),
        'nominal_calculation_seconds':nominal['seconds'],'study_seconds':s['seconds'],'zone_error':s['zone_error'],
        'nominal_unchanged':True,'raw_actions_preserved':True,'weighted_resultant_residual':float(abs(total-rebuilt).max().max()),
        'study_design_acceptance':False,'study_status':s['status'],'criteria':{'ratio_greater_than':2.,'modified_score_greater_than':3.5,'minimum_neighbours':4,'single_pass':True,'strict_local_maximum':True,'opposing_retained_neighbour_pair':True,'dc_threshold_used':False},
        'comparison':records(s['comparison']),'filtered_governors':governors,
        'input_hashes':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in [a.project,*a.exports]}}
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ['version','peak_excluded_records','peak_excluded_nodes','retained_study_records','study_seconds','filtered_governors']},indent=2,ensure_ascii=False))


if __name__=='__main__':main()
