"""Audit the supplied original DL/U2A files without changing project inputs."""
from pathlib import Path
import argparse
import hashlib
import json
from concrete_pmm_pro.analysis.csi_component_equilibrium import audit_payload, VERSION


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dl",type=Path,required=True)
    parser.add_argument("--u2a",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    result={"version":VERSION,"datasets":{}}
    for label,path,mode in (("DL",args.dl,"static"),("U2A",args.u2a,"unverified")):
        payload=path.read_bytes();digest=hashlib.sha256(payload).hexdigest()
        audit=audit_payload(payload,path.name,source_mode=mode,
            concurrency_confirmed=(mode=="static"),evidence="User-confirmed single static DL case" if mode=="static" else "")
        assert len(audit.summary)==(6 if label=="DL" else 12)
        assert len(audit.trace)==(276 if label=="DL" else 0)
        expected="EQUILIBRIUM CONSISTENT" if label=="DL" else "ENVELOPE — NO VECTOR SUM"
        assert audit.summary["Audit status"].eq(expected).all()
        for kind in ("summary","offsets","trace"):
            frame=getattr(audit,kind)
            if not frame.empty: frame.to_csv(args.output_dir/f"{label}_{kind}.csv",index=False,encoding="utf-8-sig")
        detail={"source_name":path.name,"sha256":digest,"summary_rows":len(audit.summary),
            "trace_rows":len(audit.trace),"statuses":audit.summary["Audit status"].value_counts().to_dict(),
            "source_unchanged":hashlib.sha256(path.read_bytes()).hexdigest()==digest}
        assert detail["source_unchanged"]
        if label=="DL":
            detail.update(max_force_residual_kN=float(audit.summary["Max force residual kN"].max()),
                max_moment_residual_kNm=float(audit.summary["Max moment residual kN-m"].max()),
                max_holdout_moment_residual_kNm=float(audit.summary["Holdout moment residual kN-m"].max()))
            selected=audit.trace[audit.trace["Girder"].eq("Interior Girder 2")]
            peak=selected.loc[selected["Girder T"].abs().idxmax()]
            detail["peak_interior2_torque"]={k:(peak[k].item() if hasattr(peak[k], "item") else peak[k]) for k in ("Station x (m)","Occurrence",
                "Beam T at B kN-m","Slab T at S kN-m","Beam r2V3 kN-m","Slab r2V3 kN-m",
                "Beam -r3V2 kN-m","Slab -r3V2 kN-m","Rebuilt T","Girder T","Residual T")}
        result["datasets"][label]=detail
    (args.output_dir/"EQUILIBRIUM27_actual_review.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__": main()
