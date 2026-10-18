"""Recheck saved governors without section preparation or a solver rerun."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from concrete_pmm_pro.analysis.igird_composite_steel45 import Supplies
from concrete_pmm_pro.verification.igird_fullvt48 import audit_witness,design_evidence


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    snapshots=json.loads(args.scan.read_text());records=[]
    for snapshot in snapshots:
        seen=set()
        for item in snapshot['rows']+snapshot['governing_rows']:
            key=(item['Girder'],item['Source input ordinal'])
            if key in seen:continue
            seen.add(key)
            supply=Supplies(**item['calculation']['supplies']);a=item['actions'];audits={}
            for action,actions in [('V',{'vu_N':1000.,'tu_Nmm':0.}),('T',{'vu_N':0.,'tu_Nmm':1e6}),('VT',a),
                ('V_fixed_MN',{**a,'vu_N':1000.,'tu_Nmm':0.}),('T_fixed_MN',{**a,'vu_N':0.,'tu_Nmm':1e6})]:
                audited=audit_witness(supply,item['calculation'][action],**actions)
                assert audited['status']=='PASS',(key,action,audited)
                audits[action]=audited
            records.append({'girder':item['Girder'],'excel_row':item['Source Excel row'],'audits':audits})
    result={'status':'PASS','scope':'Independent physical-unit balances of retained governors only; not structural validation',
        'unique_source_witnesses':len(records),'individual_witnesses':sum(len(r['audits']) for r in records),
        'maximum_relative_error':max(a['maximum_relative_error'] for r in records for a in r['audits'].values()),
        'records':records,'design_evidence':[design_evidence(s) for s in snapshots]}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('records','design_evidence')}))


if __name__=='__main__':main()
