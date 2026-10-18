"""Compare saved VN49/COMPOSITE50 outcomes on identical original source rows."""
import argparse
import json
import math
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--current',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    old=json.loads(args.baseline.read_text());new=json.loads(args.current.read_text())
    keys=['Model Vn (kN), M=N=0','Model Tn (kN-m), M=N=0','V-only D/C, actual M/N',
          'T-only D/C, actual M/N','Model nominal V–T D/C']
    changed={k:0 for k in keys};governors=[];matched=0;max_force_error=0.
    def identity(row):return row['Girder'],row['Source input ordinal']
    old_rows={identity(r):r for snapshot in old for r in snapshot['station_rows']}
    new_rows={identity(r):r for snapshot in new for r in snapshot['station_rows']}
    assert old_rows.keys()==new_rows.keys()
    for key,b in new_rows.items():
        a=old_rows[key];matched+=1
        assert a['CSI actions']==b['CSI actions'] and a['Actions used']==b['Actions used']
        assert b['Independent force audit']=='PASS'
        max_force_error=max(max_force_error,b['Maximum independent force error'])
        for name in keys:
            if not math.isclose(a[name],b[name],rel_tol=1e-10,abs_tol=1e-8):changed[name]+=1
    old_members={s['coverage'][0]['Girder']:s for s in old}
    for snapshot in new:
        member=snapshot['coverage'][0]['Girder'];prior=old_members[member]
        for action in ('V','T','VT'):
            e=next(x for x in snapshot['governing_rows'] if x['Governing action']==action)
            old_e=next(x for x in prior['governing_rows'] if x['Governing action']==action)
            field={'V':'model_V_only_actual_MN_DC','T':'model_T_only_actual_MN_DC','VT':'model_VT_DC'}[action]
            governs={'Girder':member,'action':action,'baseline_governing_x_m':old_e['x (m)'],
                'current_governing_x_m':e['x (m)'],'baseline_governing_DC':old_e['calculation'][field],
                'current_governing_DC':e['calculation'][field],
                'Case':e['Case'],'Step':e['Source StepType'],'Location':e['Source location type'],
                'Source Excel row':e['Source Excel row'],
                'current_model_Vn_actual_MN_kN':e['calculation']['model_V_only_actual_MN_kN'],
                'current_model_Tn_kNm':e['calculation']['model_Tn_kNm'],
                'same_source_row_baseline':old_rows[identity(e)],
                'same_source_row_current':new_rows[identity(e)]}
            governors.append(governs)
    record={'release':'IGIRDER-COMPOSITE50','baseline':'IGIRDER-VN49',
        'matched_source_vectors':matched,'source_forces_and_used_actions_unchanged':True,
        'changed_row_counts':changed,'max_independent_force_error':max_force_error,
        'governing_comparisons':governors,
        'structural_validation':False,'accepted_full_composite_design':False}
    args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in record.items() if k!='governing_comparisons'},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
