"""Compare Analysis and Summary ULS currency without running a solver.

The empty, signed entries are a metadata regression fixture, not project
engineering results. Nothing is written to the supplied project or its cache.
"""
from pathlib import Path
import argparse
import json
import sys


def run(project, output, root, expect_rejected):
    sys.path.insert(0, str(root))
    import pandas as pd
    import app
    from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json
    from concrete_pmm_pro.ui import analysis_page as ap
    state = {}
    apply_project_to_session_state(project_from_json(project.read_text()), state)
    active = ap._active_beam_uls_demand_dataframe_from_session(state)
    route = ap._beam_uls_strength_route_from_state(state, is_bridge=True, is_building=False)
    def signature(name):
        if name == 'Flexure — Construction':
            _, rows, _ = ap._beam_uls_construction_demand_from_state(state)
            return ap._beam_uls_construction_flexure_hash(state, rows, strength_route=route)
        if name == 'Flexure — Final Composite':
            rows = active.loc[pd.to_numeric(active.Mux, errors='coerce').notna()].copy()
            return ap._beam_uls_final_composite_flexure_hash(state, rows, strength_route=route)
        if name == ap._IGIRDER_INTERFACE_SHEAR_CHECK_NAME:
            return ap._igird_interface_shear_hash(state, ap._igird_interface_source_dataframe(active),
                settings=ap._igird_interface_shear_settings_from_state(state), strength_route=route)
        return ap._beam_uls_check_input_hash(state, active, strength_route=route, check_name=name)
    names=['Flexure — Construction','Flexure — Final Composite',ap._IGIRDER_INTERFACE_SHEAR_CHECK_NAME,
        'Shear','Torsion','Shear + Torsion']
    for name in names:
        entry={'result_version':ap._IGIRDER_INTERFACE_SHEAR_RESULT_VERSION} if name==ap._IGIRDER_INTERFACE_SHEAR_CHECK_NAME else {}
        ap._beam_uls_store_manual_result(state,name,input_hash=signature(name),result=entry)
    fresh=list(app._results_beam_uls_cache(state))
    assert set(fresh)==set(names)
    state['section_parameters']=dict(state['section_parameters'])
    state['section_parameters']['Tslab_mm']+=10.
    analysis_rejects={name:ap._beam_uls_current_cached_result(state,name,signature(name)) is None for name in names}
    retained=list(app._results_beam_uls_cache(state))
    assert all(analysis_rejects.values())
    if expect_rejected:assert not retained
    evidence={'metadata_fixture_only':True,'engineering_solvers_called':0,
        'source_project_modified':False,'controlled_change':'Tslab_mm + 10 mm in disposable state',
        'fresh_entries':fresh,'analysis_rejects_stale':analysis_rejects,
        'summary_retains_stale_entries':retained,'all_stale_entries_rejected':not retained}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence,indent=2),flush=True)
    return evidence


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repo-root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--expect-rejected',action='store_true')
    args=parser.parse_args()
    run(args.project,args.output,args.repo_root,args.expect_rejected)
