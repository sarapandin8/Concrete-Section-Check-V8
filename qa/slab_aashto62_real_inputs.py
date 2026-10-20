"""Reproduce directional AASHTO checks from unchanged native project exports.

python qa/slab_aashto62_real_inputs.py --project PROJECT.json --exports A.xlsx B.xlsx C.xlsx D.xlsx --output OUTPUT_DIRECTORY
Output is an audit, not a Project JSON result cache or design certificate.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import numpy as np
from concrete_pmm_pro.analysis import slab_aashto62 as code
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
from concrete_pmm_pro.io.slab_shell_import import parse_files, BANK_KEY, PENDING_KEY


def run(project, exports, output):
    state={}
    apply_project_to_session_state(project_from_json(project.read_text(encoding='utf-8')),state)
    uploads=[]
    for path in exports:
        stream=BytesIO(path.read_bytes());stream.name=path.name;uploads.append(stream)
    package=parse_files(uploads)
    if not package.ready:
        raise ValueError(f'Incomplete source package: {package.errors}; missing {[s.title for s in package.missing]}')
    state[BANK_KEY]=package;state[PENDING_KEY]=package.signature
    result=code.calculate(state)
    output.mkdir(parents=True,exist_ok=True)
    result['summary'].to_csv(output/'AASHTO62_Check_Summary.csv',index=False,encoding='utf-8-sig')
    result['coverage'].to_csv(output/'AASHTO62_Source_Coverage.csv',index=False,encoding='utf-8-sig')
    result['exclusion_counts'].to_csv(output/'AASHTO62_Exclusion_Counts.csv',index=False,encoding='utf-8-sig')
    result['peak_ledger'].to_csv(output/'AASHTO62_Peak_Ledger.csv',index=False,encoding='utf-8-sig')
    result['axes'].to_csv(output/'AASHTO62_Axes.csv',index=False,encoding='utf-8-sig')
    def records(frame):
        return json.loads(frame.to_json(orient='records',force_ascii=False))
    rows=result['rows'];kept=rows.loc[rows[INCLUDED]]
    report={key:result[key] for key in ('version','code','source_rows','design_rows','excluded_rows',
        'geometry_excluded_rows','peak_excluded_rows','incomplete','seconds','component_status','status','scope')}
    native=package.tables['forces'].loc[package.tables['forces']['Area'].isin(set(result['geometry'].corners['Area']))].reset_index(drop=True)
    source_actions=['F11','F22','F12','M11','M22','M12','V13','V23']
    source_keys=['Area','AreaElem','Joint','OutputCase','StepType']
    actions_preserved=bool(np.array_equal(native[source_actions].to_numpy(),rows[source_actions].to_numpy()))
    keys_preserved=bool(native[source_keys].equals(rows[source_keys]))
    if not actions_preserved or not keys_preserved:
        raise AssertionError('Source action or row identity changed')
    report.update({'summary':records(result['summary']),'coverage':records(result['coverage']),
        'steel':{'area_mm2_m':result['steel'].area.tolist(),'centres_mm':result['steel'].centre.tolist(),'fc_MPa':result['steel'].fc},
        'input_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [project,*exports]},
        'all_eight_source_actions_preserved':actions_preserved,'all_source_keys_preserved':keys_preserved,
        'full_deck_design_acceptance':False,
        'excluded_have_no_numeric_checks':bool(rows.loc[~rows[INCLUDED],[c for c,_ in code.VIEWS.values()]].isna().all().all()),
        'unique_native_thicknesses':int(kept['Thickness (mm)'].nunique()),
        'direction_procedures':{d:kept[d+' procedure'].value_counts().to_dict() for d,*_ in code.AXES}})
    (output/'AASHTO62_Verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('source_rows','design_rows','geometry_excluded_rows','peak_excluded_rows','seconds','component_status')},indent=2))
    print(result['summary'].to_string(index=False))
    return state,result,report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--exports',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.project,args.exports,args.output)


if __name__=='__main__':
    main()
