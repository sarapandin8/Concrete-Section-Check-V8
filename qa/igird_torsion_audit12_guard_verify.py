"""An isolated midspan result distinguishes review from code failure.

The full member includes separate generated critical shear sections; those
remain in the production check and may legitimately fail. This UI exercise
isolates only the stated physical load station, not member acceptance.
"""
import json
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),"tests"]
from streamlit.testing.v1 import AppTest
from qa.igird_torsion_audit12 import hypothetical_state
from test_igird_uls7_concurrent_vt import check,physical

OUT=Path('qa/evidence/igird_torsion_audit12/ui_guard')
OUT.mkdir(parents=True,exist_ok=True)
results=[]
for tu,expected in [(450,"REVIEW"),(500,"FAIL")]:
    df=check(hypothetical_state(),x=10,mux=2500,vu=300,tu=tu)
    assert physical(df)["Status"]==expected
    full_statuses=df["Status"].value_counts().to_dict()
    df=df.loc[df["Station type"].eq("LOAD STATION")
        & df["Tension face"].eq("BOTTOM")].copy()
    assert len(df)==1
    csv=OUT/f"tu_{tu}.csv"
    df.to_csv(csv,index=False)
    app="\n".join(["import pandas as pd",
        "from concrete_pmm_pro.ui.igird_combined_vt import render_workspace",
        f"df=pd.read_csv({str(csv.resolve())!r})",
        "render_workspace(df,code_label='AASHTO LRFD',show_chart=False)"])
    at=AppTest.from_string(app,default_timeout=30).run()
    assert not at.exception,[e.message for e in at.exception]
    warnings=[w.value for w in at.warning]
    assert any("Additional conservative Veff" in w for w in warnings)
    if expected=="REVIEW":
        assert not at.error
        assert not at.success
    else:
        assert any("fails" in e.value for e in at.error)
    results.append({"Tu":tu,"status":expected,"exceptions":0,
        "scope":"physical midspan load station only; not member acceptance",
        "full_member_status_counts":full_statuses,
        "additional_screen_warning":True,"code_failure_error":expected=="FAIL"})
(OUT/'ui_guard_verification.json').write_text(json.dumps({"status":"PASS","cases":results},indent=2))
print(json.dumps(results))
