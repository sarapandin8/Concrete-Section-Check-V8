"""Current-input checks and separately rechecked reinforcement proposals."""
from pathlib import Path
import argparse
import json
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from qa.slab_top65_real_inputs import run as current_run
from concrete_pmm_pro.analysis import slab_design66 as design,slab_top65 as current,slab_aashto63 as code


def run(project,exports,output,*,render=False):
    started=time.monotonic()
    state,actual,original=current_run(project,exports,output/'current_inputs',render=render)
    state[current.RESULT_KEY]=actual
    result=design.calculate(state)
    proposal=result['reinforcement_proposal']
    assert result['rows'] is actual['rows']
    pd.testing.assert_frame_equal(result['summary'],actual['summary'])
    assert np.all(np.asarray(proposal['spacing'])<=actual['steel'].spacing)
    for name,key in [('Proposed_Four_Mats','mats'),('Proposed_Section_Checks','summary'),
        ('Proposed_Governing_Vectors','governors'),('Trial_History','history'),('Remaining_Shear','shear')]:
        proposal[key].to_csv(output/('DESIGN66_'+name+'.csv'),index=False,encoding='utf-8-sig')
    comparison=actual['summary'][['Check','Status','Max D/C']].merge(
        proposal['summary'][['Check','Status','Max D/C']],on='Check',suffixes=(' current',' proposed'),validate='one_to_one')
    comparison.to_csv(output/'DESIGN66_Current_vs_Proposed.csv',index=False,encoding='utf-8-sig')
    # Re-evaluate each stored governor on its own, using its original signed
    # N/M/V vector and the candidate's actual bar areas / mat levels.
    candidate=design.with_spacing(actual['steel'],proposal['spacing'])
    for _,row in proposal['governors'].iterrows():
        col=code.VIEWS[row.Check][0]
        check=code.section_checks(pd.DataFrame([row]),candidate).iloc[0]
        assert abs(float(row['D/C'])-float(check[col]))<1e-10
    report={'version':design.VERSION,'current_input_result_unchanged':True,
        'all_eight_native_actions_preserved':original['all_eight_native_actions_preserved'],
        'source_rows':result['source_rows'],'retained_rows':result['design_rows'],
        'proposal':{k:proposal[k] for k in ('status','changed','trials','known_rebar_checks_satisfied',
            'spacing','diameter','native_rechecked','face_rechecked','concrete_shear_has_failures',
            'minimum_trial_spacing','applied_to_project','full_deck_acceptance','seconds','scope')},
        'comparison':json.loads(comparison.to_json(orient='records')),
        'candidate_governors_individually_rechecked':True,'designer_seconds':result['design66_seconds'],
        'total_including_import_and_checks_seconds':time.monotonic()-started,
        'new_udl_reanalysis_available':False,'overall_project_acceptance_unchanged':result['status']}
    (output/'DESIGN66_Verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
    (output/'DESIGN66_Current_and_Proposal_Report.zip').write_bytes(design.report_zip(result))
    print(json.dumps({k:report[k] for k in ('version','source_rows','retained_rows','proposal','designer_seconds')},indent=2),flush=True)
    print(comparison.to_string(index=False),flush=True)
    return state,result,report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--exports',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args()
    run(args.project,args.exports,args.output,render=args.render)
