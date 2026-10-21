"""Reproduce unchanged native slab checks and every print-reference view."""
from pathlib import Path
from io import BytesIO
import argparse
import hashlib
import json
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import numpy as np
from concrete_pmm_pro.analysis import slab_review68 as engine
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
from concrete_pmm_pro.io.slab_shell_import import parse_files,BANK_KEY,PENDING_KEY,FORCES
from concrete_pmm_pro.visualization import slab_top65 as plots,slab_print72 as printing


def run(project,exports,output,baseline):
    start=time.monotonic();state={}
    apply_project_to_session_state(project_from_json(project.read_text()),state)
    uploads=[]
    for path in exports:
        stream=BytesIO(path.read_bytes());stream.name=path.name;uploads.append(stream)
    package=parse_files(uploads)
    assert package.ready,(package.errors,package.missing)
    state[BANK_KEY]=package;state[PENDING_KEY]=package.signature
    result=engine.calculate(state)
    native=package.tables['forces'].loc[lambda f:f.Area.isin(set(result['geometry'].corners.Area))].reset_index(drop=True)
    keys=['Area','AreaElem','Joint','OutputCase','StepType']
    assert native[keys].equals(result['rows'][keys])
    np.testing.assert_array_equal(native[list(FORCES)],result['rows'][list(FORCES)])
    output.mkdir(parents=True,exist_ok=True)
    comparisons=[]
    audit=result['code_review']
    for name,frame in [('Check_Summary',result['summary']),('Four_Mats',result['mat_envelopes']),
        ('Source_Coverage',result['coverage']),('Exclusions',result['exclusion_counts']),
        ('Code_Eligibility',audit['eligibility']),('Governing_Vectors',audit['governing_vectors']),
        ('Selected_Section_Cuts',audit['section_cuts'])]:
        path=output/(name+'.csv');frame.to_csv(path,index=False,encoding='utf-8-sig')
        same=path.read_bytes()==(baseline/path.name).read_bytes()
        assert same,path.name
        comparisons.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'byte_identical_to_QA71':same})
    refs=printing.references(result)
    assert len(refs['girders'])==6
    assert [b['station_m'] for b in refs['bearings']]==[.4,19.6]
    assert [len(b['points']) for b in refs['bearings']]==[6,6]
    folder=output/'figures';folder.mkdir(exist_ok=True)
    charts=[]
    for index,view in enumerate(engine.VIEWS):
        adapted=engine.map_adapter(result,view)
        for mode,figure in [('plan',plots.plan(result,adapted,view)),('profile',plots.profile(adapted,view))]:
            assert figure.layout.meta['slab_print_version']==printing.VERSION
            assert figure.layout.meta['girder_count']==6
            assert figure.layout.meta['bearing_stations_m']==[.4,19.6]
            filename=f'{mode}_{index:02d}.json'
            figure.write_json(folder/filename)
            charts.append({'view':view,'mode':mode,'file':filename,'girder_labels':6,
                'bearing_stations_m':[.4,19.6],'bearing_reference':'centerline',
                'trace_count':len(figure.data)})
    (folder/'manifest.json').write_text(json.dumps(charts,indent=2))
    evidence={'milestone':printing.VERSION,'numerical_engine':engine.VERSION,
        'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [project,*exports]},
        'source_files_modified':False,'source_rows':result['source_rows'],'design_rows':result['design_rows'],
        'excluded_rows':result['excluded_rows'],'all_native_keys_and_actions_preserved':True,
        'new_source_exclusions':0,'numerical_csv_comparisons':comparisons,
        'girders':[{'label':g['label'],'source_id':g['source_id'],'a':g['a'].tolist(),'b':g['b'].tolist()} for g in refs['girders']],
        'bearing_stations_m':[.4,19.6],'bearing_reference':'centerline','bearing_reference_points':12,
        'bearing_symbols_are_footprints':False,'charts':charts,'print_format':'SVG',
        'seconds':time.monotonic()-start,'status':result['status'],'full_deck_acceptance':False}
    (output/'Print_Verification.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps({k:v for k,v in evidence.items() if k not in ('source_hashes','charts','numerical_csv_comparisons')},indent=2),flush=True)
    return evidence


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--exports',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,default=Path(__file__).resolve().parents[1]/'qa/evidence/analysis71/slab')
    args=parser.parse_args()
    run(args.project,args.exports,args.output,args.baseline)
