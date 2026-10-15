"""Prepare the user's chosen independent dowel draft; do not infer extents."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from concrete_pmm_pro.analysis.igird_interface_connectors import at_station, INDEPENDENT_DOWELS
from concrete_pmm_pro.io.girder_csi_import import read_tables, prepare_csi_table
from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
from concrete_pmm_pro.ui import analysis_page as ap


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--dl',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    original=json.loads(args.project.read_text());draft=deepcopy(original)
    key='beam_girder_interface_shear_settings'
    previous=original['metadata'][key]
    # Retain the existing anchorage declaration as declared project information,
    # not as a new development-length verification from the two photographs.
    cfg={**previous,'connector_source':INDEPENDENT_DOWELS,'dowel_crossing_legs':2,
        'connectors_cross_and_anchored':bool(previous.get('connectors_cross_and_anchored',previous.get('stirrups_cross_and_anchored',False))),
        'stirrups_cross_and_anchored':False,'dowel_zones':[
            {'Zone':label+' — enter longitudinal range','x_start_m':None,'x_end_m':None,
                'Diameter_mm':12.,'Legs':2,'Spacing_mm':float(spacing),'fy_MPa':390.}
            for label,spacing in (('C–C',70),('D–D',150),('E–E',200))]}
    draft['metadata'][key]=cfg
    draft['metadata'].pop('analysis_results',None)  # Never retain results for changed connector inputs.
    copied=deepcopy(draft);copied['metadata'][key]=previous
    if 'analysis_results' in original['metadata']:copied['metadata']['analysis_results']=original['metadata']['analysis_results']
    assert copied==original,'Unexpected change outside connector inputs / obsolete results'
    path=args.output_dir/'I_Girder_20m_DOWEL28_DRAFT.json'
    path.write_text(json.dumps(draft,ensure_ascii=False,indent=2,allow_nan=False))
    state={};apply_project_to_session_state(project_from_json(path.read_text()),state)
    restored=ap._igird_interface_shear_settings_from_state(state)
    assert restored==cfg
    assert all(not at_station(restored,x_m=x)['ready'] for x in (0.,10.,20.))
    payload=args.dl.read_bytes();sha=hashlib.sha256(payload).hexdigest()
    raw=read_tables(payload,args.dl.name)['Interior Girder 1']
    parsed=prepare_csi_table(raw,sheet_name='Interior Girder 1',case_name='DL',source_name=args.dl.name,
        source_mode='static',concurrency_confirmed=True,evidence='User-confirmed static DL')
    assert not parsed.errors
    demand=parsed.frame.loc[parsed.frame['Station x (m)'].sub(10.45714).abs()<1e-6].iloc[[0]].copy()
    prep,composite,messages=ap._beam_uls_final_composite_preparation(state)
    assert composite is not None,messages
    route=ap.beam_girder_uls_strength_route(is_bridge=True,is_building=False,project_design_code='AASHTO LRFD',code_edition='2020')
    result,messages=ap._igird_interface_shear_dataframe(state,demand,prep=prep,composite_state=composite,
        settings=restored,strength_route=route)
    assert result['Status'].eq('REVIEW').all()
    assert result['Avf credited (mm2/m)'].eq(0).all()
    assert all('dowel' in str(x).lower() for x in result['Reason'])
    quantities=[]
    for record in cfg['dowel_zones']:
        # Local numerical probe only; this artificial coverage is never saved
        # to the user's draft or used as a full-span engineering result.
        probe=deepcopy(record);probe.update(x_start_m=0.,x_end_m=1.)
        area=at_station({**cfg,'dowel_zones':[probe]},x_m=.5)['zone']['Avf_mm2_per_m']
        quantities.append({'label':record['Zone'],'db_mm':12,'crossing_legs':2,
            'spacing_mm':record['Spacing_mm'],'Avf_mm2_per_m':area})
    result.to_csv(args.output_dir/'DOWEL28_actual_DL_pending_range.csv',index=False,encoding='utf-8-sig')
    report={'version':'IGIRDER.DOWEL28','draft_file':path.name,'raw_loads_and_other_inputs_preserved':True,
        'dowel_extents_inferred':False,'draft_actual_DL_status':list(result['Status']),
        'draft_credited_Avf_mm2_per_m':list(result['Avf credited (mm2/m)']),
        'quantities_from_drawing':quantities,'source_project_sha256':hashlib.sha256(args.project.read_bytes()).hexdigest(),
        'source_DL_sha256':sha,'source_DL_unchanged':hashlib.sha256(args.dl.read_bytes()).hexdigest()==sha,
        'transition_spacing_in_original_I_table_mm':100,'dowel_DD_spacing_in_drawing_mm':150}
    (args.output_dir/'DOWEL28_actual_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
