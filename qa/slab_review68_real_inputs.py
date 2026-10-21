"""Reproduce REVIEW68 with four native CSI exports and an input-only project.

--example-mats explicitly replaces only the four screenshot mat sizes/spacings:
longitudinal and transverse DB16@150 top / DB20@150 bottom, transverse cover40.
It does not verify aggregate, change loads, or represent the unmodified JSON.
"""
from pathlib import Path
from io import BytesIO
import argparse
import hashlib
import json
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import numpy as np

from concrete_pmm_pro.analysis import slab_review68 as review
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
from concrete_pmm_pro.io.slab_shell_import import parse_files,BANK_KEY,PENDING_KEY,FORCES


def apply_example_mats(state):
    """An explicit QA scenario, never called by the product UI."""
    parameters=state['section_parameters']
    mesh=state['beam_girder_interface_shear_settings']['dowel_connection']['slab_transverse_mesh']
    for face,diameter in [('top',16.),('bottom',20.)]:
        parameters[f'deck_long_rebar_{face}_diameter_mm']=diameter
        parameters[f'deck_long_rebar_{face}_spacing_mm']=150.
        mesh[face].update(Diameter_mm=diameter,Spacing_mm=150.,Clear_cover_mm=40.)


def run(project,exports,output,*,example_mats=False):
    started=time.monotonic()
    state={}
    apply_project_to_session_state(project_from_json(project.read_text(encoding='utf-8')),state)
    if example_mats:
        apply_example_mats(state)
    uploads=[]
    for path in exports:
        file=BytesIO(path.read_bytes());file.name=path.name;uploads.append(file)
    package=parse_files(uploads)
    if not package.ready:
        raise ValueError(str(package.errors)+str([s.title for s in package.missing]))
    state[BANK_KEY]=package;state[PENDING_KEY]=package.signature
    result=review.calculate(state)
    native=package.tables['forces'].loc[lambda f:f.Area.isin(set(result['geometry'].corners.Area))].reset_index(drop=True)
    keys=['Area','AreaElem','Joint','OutputCase','StepType']
    assert native[keys].equals(result['rows'][keys])
    np.testing.assert_array_equal(native[list(FORCES)],result['rows'][list(FORCES)])
    audit=result['code_review']
    output.mkdir(parents=True,exist_ok=True)
    for name,frame in [('Check_Summary',result['summary']),('Four_Mats',result['mat_envelopes']),
        ('Source_Coverage',result['coverage']),('Exclusions',result['exclusion_counts']),
        ('Code_Eligibility',audit['eligibility']),('Governing_Vectors',audit['governing_vectors']),
        ('Selected_Section_Cuts',audit['section_cuts'])]:
        frame.to_csv(output/(name+'.csv'),index=False,encoding='utf-8-sig')
    verification={'milestone':review.VERSION,'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [project,*exports]},
        'example_mats_explicitly_applied':example_mats,'example_mats':'DB16@150 top / DB20@150 bottom both directions; transverse clear cover40mm' if example_mats else None,
        'source_rows':result['source_rows'],'design_rows':result['design_rows'],'excluded_rows':result['excluded_rows'],
        'local_transfer_native_records':int((result['rows'][INCLUDED]&result['rows']['Longitudinal local support region']).sum()),
        'all_native_keys_and_actions_preserved':True,'new_source_exclusions':0,'exceptions_applied':audit['exceptions_applied'],
        'aggregate_used_mm':result['aggregate_used_mm'],'status':result['status'],'full_deck_acceptance':False,
        'section_cut_count':len(audit['section_cuts']),'section_cuts_complete':int(audit['section_cuts'].get('Source coverage',[]).sum()) if len(audit['section_cuts']) else 0,
        'cut_errors':audit['cut_errors'],'seconds':time.monotonic()-started,
        'summary':json.loads(result['summary'].to_json(orient='records')),
        'governing_vectors':json.loads(audit['governing_vectors'].to_json(orient='records'))}
    (output/'Real_File_Verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (output/'Top_Slab_Review68.zip').write_bytes(review.report_zip(result))
    print(json.dumps({k:v for k,v in verification.items() if k not in ('summary','governing_vectors','source_hashes')},ensure_ascii=False,indent=2),flush=True)
    print(result['summary'].to_string(index=False),flush=True)
    return verification


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--exports',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--example-mats',action='store_true')
    args=parser.parse_args()
    run(args.project,args.exports,args.output,example_mats=args.example_mats)
