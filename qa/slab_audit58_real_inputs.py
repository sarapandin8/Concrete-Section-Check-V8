"""Reproduce AUDIT58 using the user's unchanged JSON and complete CSI exports.

Run from the repository root:
python qa/slab_audit58_real_inputs.py --project PROJECT.json --exports A.xlsx B.xlsx C.xlsx D.xlsx --output audit58.json
The JSON output is a diagnostic record, not a production result cache.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from concrete_pmm_pro.analysis import slab_shell56 as engine
from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state
from concrete_pmm_pro.io.slab_shell_import import parse_files,BANK_KEY,PENDING_KEY


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--exports',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    state={}
    apply_project_to_session_state(project_from_json(args.project.read_text(encoding='utf-8')),state)
    uploads=[]
    for path in args.exports:
        file=BytesIO(path.read_bytes());file.name=path.name;uploads.append(file)
    package=parse_files(uploads)
    state[BANK_KEY]=package;state[PENDING_KEY]=package.signature
    result=engine.calculate(state)
    rows=result['rows']
    def records(frame):
        return json.loads(frame.to_json(orient='records',force_ascii=False))
    report={'version':result['version'],'code':result['code'],'source_rows':result['source_rows'],
        'elements':len(result['geometry'].elements),'seconds':result['seconds'],
        'status':result['status'],'counts':result['counts'],
        'nm_peak':float(rows['N–M field D/C'].max()),
        'known_component_peak':float(rows['Field D/C'].max()),
        'equilibrium_residual_max':float(rows['Equilibrium residual'].max()),
        'shear_review_records':int(rows['Shear D/C'].isna().sum()),
        'combined_review_records':int(rows['Combined N–M–V status'].eq('REVIEW').sum()),
        'coverage':records(result['coverage']),'steel_summary':records(result['summary']),
        'check_summary':records(result['check_summary']),'scope':result['scope'],
        'input_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [args.project,*args.exports]}}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(f"{result['version']}: {len(rows):,} rows; N-M peak {report['nm_peak']:.6f}; known-component peak {report['known_component_peak']:.6f}")


if __name__=='__main__':
    main()
