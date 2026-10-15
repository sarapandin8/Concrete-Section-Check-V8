"""Read-only real-file transport audit; prepare a separate configured JSON."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pandas as pd
from concrete_pmm_pro.io import csi_force_reference as ref
from concrete_pmm_pro.io.girder_csi_import import read_tables, prepare_csi_table, source_info
from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
from concrete_pmm_pro.ui import analysis_page as ap, igird_station_section as station
from concrete_pmm_pro.ui.csi_reference_analysis import convert_for_check


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--project",type=Path,required=True)
    parser.add_argument("--dl",type=Path,required=True)
    parser.add_argument("--u2a",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    before={str(p):digest(p) for p in (args.project,args.dl,args.u2a)}
    cfg=ref.canonical_profile({"depth_below_deck_top_m":1.85-1.2344,
        "source_top_y_m":1.85,"source_cg_y_m":1.2344,
        "section_name":"I-Girder","vertical_location":"CG of Full Bridge Section",
        "force_kind":"GIRDER_COMPOSITE",
        "basis":"User CSI screenshots 20261014-110711 and 110915; displayed Y values"})
    original=json.loads(args.project.read_text())
    configured=deepcopy(original)
    configured["metadata"][ref.SETTINGS_KEY]=cfg
    changed={}
    for name, rows in configured["metadata"].get("workflow_load_tables",{}).items():
        if not isinstance(rows,list) or not rows:
            continue
        frame=pd.DataFrame(rows)
        if "Note" not in frame:
            continue
        bound=ref.bind_reference(frame,cfg)
        count=int(frame["Note"].fillna("").ne(bound["Note"].fillna("")).sum())
        if count:
            pd.testing.assert_frame_equal(frame.drop(columns="Note"),bound.drop(columns="Note"))
            for index, existing in enumerate(rows):
                existing["Note"] = bound.iloc[index]["Note"]
            changed[name]=count
    output_project=args.output_dir/"I_Girder_20m_CSIREF26.json"
    output_project.write_text(json.dumps(configured,ensure_ascii=False,indent=2,allow_nan=False))
    (args.output_dir/"CSiBridge_reference_Current_I_Girder.json").write_text(
        json.dumps(cfg,ensure_ascii=False,indent=2,allow_nan=False))
    state={}
    apply_project_to_session_state(project_from_json(output_project.read_text()),state)
    route=ap.beam_girder_uls_strength_route(is_bridge=True,is_building=False,
        project_design_code="AASHTO LRFD",code_edition="2020")
    _,composite,notes=ap._beam_uls_final_composite_preparation(state)
    if composite is None:
        raise ValueError("; ".join(notes))
    result={"version":ref.VERSION,"source_profile":cfg,"input_hashes":before,
        "configured_rows":changed,"raw_loads_preserved":True,"datasets":{}}
    for path,case,mode in ((args.dl,"DL","static"),(args.u2a,"U2A","unverified")):
        table=read_tables(path.read_bytes(),path.name)["Interior Girder 1"]
        parsed=prepare_csi_table(table,sheet_name="Interior Girder 1",case_name=case,
            source_name=path.name,source_mode=mode,concurrency_confirmed=mode=="static",
            evidence="User-confirmed static DEAD/DL" if mode=="static" else "")
        if parsed.errors:
            raise ValueError(parsed.errors)
        bound=ref.prepare_analysis_frame(ref.bind_reference(parsed.frame,cfg))
        records=[]
        max_roundtrip=0.
        modes={}
        for _,row in bound.iterrows():
            local=station.at_station(composite,row["Station x (m)"])
            shifted=convert_for_check(local,row,check_name="Flexure")
            trace=shifted[ref.RUNTIME_KEY]
            modes[trace["mode"]]=modes.get(trace["mode"],0)+1
            if trace["mode"]=="EXACT":
                restored=ref.transport(trace["transported_actions"],
                    r2_m=-trace["r2_m"],r3_m=-trace["r3_m"])
                max_roundtrip=max(max_roundtrip,max(abs(restored[f]-trace["original_actions"][f]) for f in ref.FIELDS))
            records.append({"x_m":row["Station x (m)"],"source_step":source_info(row)["step"],
                "source_row":source_info(row)["row"],"source_set":source_info(row)["occurrence"],
                **ref.trace_columns(shifted),
                **{f"At O {f}":shifted[col] for f,col in ref.ULS_MAP.items()}})
        (args.output_dir/f"{case}_Interior1_reference_audit.json").write_text(
            json.dumps(records,ensure_ascii=False,indent=2,allow_nan=False))
        result["datasets"][case]={"rows":len(records),"modes":modes,
            "roundtrip_max_abs_error":max_roundtrip,"sample":records[len(records)//2]}
        if case=="DL":
            # Real consumer validation, not only the algebraic helper.
            subset=bound.loc[bound["Station x (m)"].sub(10.45714).abs()<1e-6].iloc[[0]]
            converted=convert_for_check(station.at_station(composite,float(subset.iloc[0]["Station x (m)"])),
                subset.iloc[0],check_name="Flexure")
            ai,messages=ap._beam_uls_flexure_analysis_input_for_station(composite,row=converted,
                strength_route=route)
            if ai is None:
                raise ValueError("; ".join(messages))
            assert abs(ai.load_cases[0].Mux_Nmm/1e6-converted["Mux"])<1e-9
            result["flexure_reader_matches_transport"]=True
            calculated,messages=ap._beam_uls_flexure_preview_dataframe(composite,subset,
                strength_route=route,apply_girder_development=True)
            result["real_station_flexure"]={
                "rows":len(calculated),"status":list(calculated.get("Status",[])),
                "has_reference_trace":"Reference version" in calculated,
                "notes":messages[:3]}
    result["source_files_unchanged"]=all(digest(p)==before[str(p)] for p in (args.project,args.dl,args.u2a))
    (args.output_dir/"CSIREF26_actual_review.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps({k:v for k,v in result.items() if k not in {"datasets","source_profile","input_hashes"}},
        ensure_ascii=False))


if __name__=="__main__":
    main()
