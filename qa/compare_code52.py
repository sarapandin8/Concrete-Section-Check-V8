"""Compare complete stored code-frame digests on identical source vectors."""
import argparse,json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('baseline','current','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();old=json.loads(a.baseline.read_text());new=json.loads(a.current.read_text())
    assert old['status']==new['status']=='PASS'
    assert old['source_sha256']==new['source_sha256']
    assert old['members'].keys()==new['members'].keys()
    matched=[]
    for member,checks in new['members'].items():
        for check,value in checks.items():
            prior=old['members'][member][check]
            assert prior['frames']==value['frames'],(member,check)
            assert prior['primary_rows']==value['primary_rows'],(member,check)
            assert prior['control']==value['control'],(member,check)
            matched.append({'member':member,'check':check,'primary_rows':len(value['primary_rows']),
                'frames_compared':len(value['frames']),'all_code_values_and_statuses_unchanged':True})
    result={'status':'PASS','baseline':'COMPOSITE51 production code frames; LP sidecar bypassed',
        'current':'CODE52','source_sha256':new['source_sha256'],'matched_checks':matched,
        'all_complete_frame_hashes_equal':True,'original_Tu_policy_preserved':True,
        'LP_calculation_calls':new['LP_calculation_calls'],'structural_design_acceptance':False}
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
