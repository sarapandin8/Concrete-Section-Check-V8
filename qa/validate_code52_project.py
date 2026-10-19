"""Replay all original code checks; compare COMPOSITE51 without its LP sidecar.

No source input is rewritten. The baseline bypass is ONLY for its detached LP
payload, so the complete production code frames can be compared independently
of the research model. Baseline/current run in separate processes/import trees.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import logging
import math
from pathlib import Path
import sys
import time
from unittest.mock import patch


def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [clean(x) for x in v]
    if hasattr(v,'item'):return clean(v.item())
    if isinstance(v,float) and not math.isfinite(v):return None if math.isnan(v) else str(v)
    return v


def digest(v):
    return hashlib.sha256(json.dumps(clean(v),ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--baseline-without-LP',action='store_true')
    args=p.parse_args();sys.path.insert(0,str(args.repo.resolve()))
    for name in ('streamlit','streamlit.runtime.scriptrunner_utils.script_run_context'):
        logging.getLogger(name).setLevel(logging.ERROR)
    import pandas as pd
    from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state
    from concrete_pmm_pro.ui import analysis_page as ap,igird_composite_steel45 as research
    from concrete_pmm_pro.ui.igird_case_review import FRAME_KEYS,controlling_result,summary_record
    args.output.parent.mkdir(parents=True,exist_ok=True)
    raw=args.project.read_bytes();state={}
    apply_project_to_session_state(project_from_json(raw.decode()),state)
    params=deepcopy(state['section_parameters']);interface=deepcopy(state['beam_girder_interface_shear_settings'])
    bank=pd.DataFrame(state['igird_uls_member_bank']);original=bank.copy(deep=True)
    route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
    results={};started=time.monotonic()
    columns=['Case','Governing x','Station type','Status','Calculation status','Mu kN-m','Nu kN','Vu kN','Tu kN-m',
        'Original CSI T kN-m','T used kN-m','T shift applied','φVn kN','φTn kN-m','Vc kN','Vs kN','Vn kN',
        'D/C value','Strength D/C value','Stress D/C value','Transverse D/C value','Longitudinal D/C value',
        'Overall D/C value','Threshold status','θ deg','θ cot','dv mm','bw mm',
        'Source Excel row','Source StepType','Source LocType','Reference status','Composite action status',
        'Longitudinal status','Review reason','Notes']
    with patch.object(research,'calculate',side_effect=AssertionError('Code route must not calculate LP')) as lp:
        # 51 imports payload inside Calculate. Its code frames stay real.
        with patch.object(research,'payload',return_value={}) if args.baseline_without_LP else patch.object(
                research,'payload',side_effect=AssertionError('Code52 must not request LP')):
            for member,rows in bank.groupby('Girder',sort=False):
                # Use the same numeric/source preparation as the real app.
                # Original JSON cells stay unchanged, including numeric text.
                local=dict(state);local['beam_uls_loads_table']=rows.copy(deep=True)
                rows=ap._active_beam_uls_demand_dataframe_from_session(local)
                checks={};results[member]=checks
                for check in ('Shear','Torsion','Shear + Torsion'):
                    t=time.monotonic()
                    package=ap._beam_uls_calculate_selected_check(dict(state),rows.copy(deep=True),
                        selected_check=check,strength_route=route)
                    assert research.KEY not in package
                    frames={k:v for k,v in package.items() if isinstance(v,pd.DataFrame)}
                    primary=frames[FRAME_KEYS[check]]
                    assert not primary.empty
                    if 'T shift applied' in primary:
                        used=primary.loc[primary['T shift applied'].notna()]
                        assert not used['T shift applied'].astype(bool).any()
                        if all(k in used for k in ('Original CSI T kN-m','T used kN-m')):
                            assert used['Original CSI T kN-m'].equals(used['T used kN-m'])
                    checks[check]={'frames':{k:{'rows':len(v),'sha256':digest(v.to_dict('records'))} for k,v in frames.items()},
                        'primary_rows':clean(primary[[k for k in columns if k in primary]].to_dict('records')),
                        'status_counts':dict(Counter(primary['Status'])),
                        'control':clean(summary_record(controlling_result(primary,check))),
                        'runtime_seconds':time.monotonic()-t}
                    print(member,check,len(primary),'rows',round(time.monotonic()-t,2),'s',flush=True)
                    args.output.write_text(json.dumps(clean({'members':results,'in_progress':True}),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        assert lp.call_count==0
    assert args.project.read_bytes()==raw
    assert params==state['section_parameters'] and interface==state['beam_girder_interface_shear_settings']
    pd.testing.assert_frame_equal(bank,original)
    record={'status':'PASS','release':'COMPOSITE51 code baseline, LP detached' if args.baseline_without_LP else 'IGIRDER.CODE52',
        'source_sha256':hashlib.sha256(raw).hexdigest(),'source_rows':len(bank),'imported_girder_banks':len(results),
        'source_inputs_unchanged':True,'LP_calculation_calls':0,'members':results,
        'input_pipeline':'Real app active-demand canonicalization; source JSON unchanged',
        'runtime_seconds':time.monotonic()-started,'structural_design_acceptance':False}
    args.output.write_text(json.dumps(clean(record),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print('PASS all code frames, source unchanged, no LP',round(record['runtime_seconds'],2),'s',flush=True)


if __name__=='__main__':main()
