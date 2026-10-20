"""Reproduce SHEAR64 from Project JSON and the same four native CSI exports.

No load footprint is assumed: punching remains NOT CALCULATED without explicit
metadata inputs. Interface is a read-only link to current runtime Flexure results.
The output is an audit, not a design certificate or persistent solver cache.
"""
from pathlib import Path
import argparse,json,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from qa.slab_aashto63_real_inputs import run as accepted_run
from concrete_pmm_pro.analysis import slab_shear64 as code
from concrete_pmm_pro.ui.slab_interface64 import linked_results


def run(project,exports,output):
    state,accepted,report=accepted_run(project,exports,output/'accepted_oneway')
    start=time.monotonic()
    result=code.calculate(state,reuse=accepted)
    link=linked_results(state)
    pd.testing.assert_frame_equal(result['summary'],accepted['summary'])
    result['summary'].to_csv(output/'SHEAR64_Check_Summary.csv',index=False,encoding='utf-8-sig')
    link['rows'].to_csv(output/'SHEAR64_Linked_Interface.csv',index=False,encoding='utf-8-sig')
    p=result['punching']
    if not p['rows'].empty:p['rows'].to_csv(output/'SHEAR64_Punching.csv',index=False,encoding='utf-8-sig')
    report.update({'version':code.VERSION,'scope':result['scope'],'oneway_base_reused':result['base_reused'],
        'unchanged_oneway_summary':True,'punching_status':p['status'],'defined_punching_areas':len(p['areas']),
        'interface_status':link['status'],'interface_rows':json.loads(link['rows'].to_json(orient='records')),
        'additional_punching_and_link_seconds':time.monotonic()-start,
        'full_deck_design_acceptance':False})
    (output/'SHEAR64_Verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['version','punching_status','defined_punching_areas','interface_status','additional_punching_and_link_seconds']},indent=2))
    return state,result,report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--exports',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.project,args.exports,args.output)
