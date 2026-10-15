"""Independent component equilibrium, source identities and read-only UI."""
from copy import deepcopy
from io import BytesIO
from unittest.mock import patch
from zipfile import BadZipFile
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.analysis.csi_component_equilibrium import audit_tables, audit_payload
from concrete_pmm_pro.io.girder_csi_import import CSI_COLUMNS


def tables(*, unit="SI", envelope=False, degenerate=False, case="DL", member=1):
    values={k:[] for k in ("Girder","Beam","Slab")}
    for x in range(9):
        b=dict(P=20+7*x+1.2*x*x,V2=300-30*x,V3=1+.7*x,T=3-.2*x,M2=2+.4*x,M3=100*x*(10-x))
        s=dict(P=-8+.5*x-.2*x*x,V2=50-7*x,V3=90-9*x,T=8-2*x,M2=5+x,M3=5*x*(10-x))
        if degenerate: s["P"]=2*b["P"]
        # Direct scalar equations, independently of the implementation helper.
        g={f:b[f]+s[f] for f in b}
        g["T"]+=-.52*b["V3"]+.44*s["V3"]-.35*s["V2"]
        g["M3"]-=-.52*b["P"]+.44*s["P"]
        g["M2"]-=.35*s["P"]
        for kind,v in (("Girder",g),("Beam",b),("Slab",s)):
            factor=1 if unit=="SI" else 4.4482216152605
            mfactor=1 if unit=="SI" else 1.3558179483314
            distance=x if unit=="SI" else x/.3048
            values[kind].append([distance,distance,"Max" if envelope else "Static",
                *[v[f]/(factor if f in {"P","V2","V3"} else mfactor) for f in ("P","V2","V3","T","M2","M3")],case])
    result={}
    for kind,rows in values.items():
        units=["m","m","","kN","kN","kN","kN-m","kN-m","kN-m",""] if unit=="SI" else ["ft","ft","","kip","kip","kip","kip-ft","kip-ft","kip-ft",""]
        result[f"Interior {kind} {member}"]=pd.DataFrame([units,*rows],columns=[*CSI_COLUMNS,"OutputCase"])
    return result


def audit(t,**kwargs):
    return audit_tables(t,source_name="fixture.xlsx",source_mode="static",concurrency_confirmed=True,
        evidence="explicit single static case",**kwargs)


def test_six_force_reconstruction_and_independent_torque_terms():
    r=audit(tables())
    assert r.summary.iloc[0]["Audit status"]=="EQUILIBRIUM CONSISTENT"
    assert len(r.trace)==9 and len(r.offsets)==2
    np.testing.assert_allclose(r.offsets["C_component-C_G local2 m"],[-.52,.44],atol=1e-12)
    np.testing.assert_allclose(r.offsets["C_component-C_G local3 m"],[0,.35],atol=1e-12)
    for f in ("P","V2","V3","T","M2","M3"):
        assert r.trace[f"Residual {f}"].abs().max()<1e-10
    row=r.trace.iloc[0]
    terms=["Beam T at B kN-m","Slab T at S kN-m","Beam r2V3 kN-m","Slab r2V3 kN-m","Beam -r3V2 kN-m","Slab -r3V2 kN-m"]
    assert sum(row[t] for t in terms)==pytest.approx(row["Girder T"])
    assert row[terms[0]]+row[terms[1]]!=pytest.approx(row["Girder T"])


def test_held_out_torque_corruption_cannot_be_absorbed_by_a_torque_fit():
    t=tables();t["Interior Girder 1"].loc[2,"T"]+=1.0
    r=audit(t)
    assert r.summary.iloc[0]["Audit status"]=="EQUILIBRIUM MISMATCH"
    assert r.summary.iloc[0]["Holdout moment residual kN-m"]==pytest.approx(1)
    np.testing.assert_allclose(r.offsets["C_component-C_G local2 m"],[-.52,.44],atol=1e-12)


def test_units_are_normalized_before_identification():
    si,us=audit(tables()),audit(tables(unit="US"))
    assert us.summary.iloc[0]["Audit status"]=="EQUILIBRIUM CONSISTENT"
    for col in ("C_component-C_G local2 m","C_component-C_G local3 m"):
        np.testing.assert_allclose(si.offsets[col],us.offsets[col],atol=1e-12)
    np.testing.assert_allclose(si.trace["Girder T"],us.trace["Girder T"],atol=1e-10)


def test_component_grid_mismatch_never_pairs_partial_cut_faces():
    t=tables();t["Interior Slab 1"]=t["Interior Slab 1"].drop(index=3)
    r=audit(t)
    assert r.summary.iloc[0]["Audit status"]=="CUT MISMATCH"
    assert r.trace.empty and r.offsets.empty


def test_component_envelopes_cannot_identify_origins_even_if_correspondence_declared():
    r=audit_tables(tables(envelope=True),source_name="U2A.xlsx",source_mode="correspondence",
        concurrency_confirmed=True,evidence="each row is declared correspondence")
    assert r.summary.iloc[0]["Audit status"]=="ENVELOPE — NO VECTOR SUM"
    assert r.trace.empty and r.offsets.empty


def test_unknown_static_contract_does_not_become_a_verified_audit():
    r=audit_tables(tables(),source_name="unverified.xlsx")
    assert r.summary.iloc[0]["Audit status"]=="STATE UNVERIFIED"
    assert r.offsets.empty


def test_rank_deficient_origins_remain_unresolved():
    r=audit(tables(degenerate=True))
    assert r.summary.iloc[0]["Audit status"]=="ORIGIN UNRESOLVED"
    assert r.trace.empty


def test_members_and_cases_are_never_merged_and_girder_count_is_not_hardcoded():
    t={**tables(member=1),**tables(member=7,case="SDL")}
    r=audit(t)
    assert len(r.summary)==2 and len(r.trace)==18
    assert set(r.summary["Case"])=={"DL","SDL"}
    assert all(r.summary["Audit status"]=="EQUILIBRIUM CONSISTENT")


def test_original_tables_and_attrs_are_unchanged_and_girder_only_is_supported():
    t=tables();before=deepcopy(t);audit(t)
    for name in t: pd.testing.assert_frame_equal(t[name],before[name])
    r=audit({"Interior Girder 1":t["Interior Girder 1"]})
    assert r.summary.empty and r.trace.empty


def test_unsupported_units_are_reported_without_partial_reconstruction():
    t=tables();t["Interior Beam 1"].loc[0,"T"]="unknown-unit"
    r=audit(t)
    assert r.summary.iloc[0]["Audit status"]=="INPUT INCOMPLETE"
    assert r.trace.empty


def test_duplicate_component_sheets_are_not_silently_overwritten():
    t=tables();t["duplicate beam"]=t["Interior Beam 1"].copy()
    t["duplicate beam"]["Girder"]=["",*["Interior Beam 1"]*9]
    r=audit(t)
    assert r.summary.iloc[0]["Audit status"]=="INPUT INCOMPLETE"
    assert "Duplicate" in r.summary.iloc[0]["Reason"]


def native_tables():
    result={}
    for name,frame in tables().items():
        frame=frame.rename(columns={"ItemType":"StepType"})
        for field,value in {"BridgeObj":"B1","Girder":name,"SectCutNum":"cut",
            "LocType":"After","CaseType":"LinearStatic","StepNum":"1"}.items():
            frame[field]=["Text",*[value]*9]
        result[name]=frame
    return result


def test_native_section_faces_and_step_numbers_must_match():
    t=native_tables()
    assert audit(t).summary.iloc[0]["Audit status"]=="EQUILIBRIUM CONSISTENT"
    t["Interior Slab 1"].loc[2,"LocType"]="Before"
    assert audit(t).summary.iloc[0]["Audit status"]=="CUT MISMATCH"
    t=native_tables();t["Interior Slab 1"].loc[2,"StepNum"]="2"
    assert audit(t).summary.iloc[0]["Audit status"]=="CUT MISMATCH"


def test_arbitrary_last_step_without_a_shared_step_number_is_not_fitted():
    t=tables()
    for frame in t.values(): frame.loc[frame.index[1:],"ItemType"]="Last"
    r=audit(t)
    assert r.summary.iloc[0]["Audit status"]=="STATE UNVERIFIED"
    assert r.trace.empty


def workbook():
    payload=BytesIO()
    with pd.ExcelWriter(payload,engine="openpyxl") as writer:
        for sheet,frame in tables().items(): frame.to_excel(writer,sheet_name=sheet,index=False)
    return payload.getvalue()


def test_real_excel_reader_and_ui_are_read_only_without_extra_confirmations():
    payload=workbook()
    parsed=audit_payload(payload,"example.xlsx",source_mode="static",concurrency_confirmed=True,evidence="static case")
    assert parsed.summary.iloc[0]["Audit status"]=="EQUILIBRIUM CONSISTENT"
    script="""
import streamlit as st
from concrete_pmm_pro.ui.csi_component_equilibrium import render_component_equilibrium
class File:
    name='example.xlsx'
    def getvalue(self): return st.session_state['fixture_payload']
render_component_equilibrium([File()],source_mode='static',concurrency_confirmed=True,evidence='static case',key_prefix='qa')
"""
    at=AppTest.from_string(script)
    at.session_state['fixture_payload']=payload
    at.session_state['project_metadata']={"unchanged":True}
    at.session_state['beam_uls_loads_table']=[{"Tu":123.456}]
    at.session_state['_beam_uls_manual_calc_cache']={"sentinel":"retained"}
    at.run(timeout=30)
    assert not at.exception and not at.checkbox
    assert len(at.dataframe)==3
    assert at.session_state['project_metadata']=={"unchanged":True}
    assert at.session_state['beam_uls_loads_table']==[{"Tu":123.456}]
    assert at.session_state['_beam_uls_manual_calc_cache']=={"sentinel":"retained"}


def test_optional_audit_does_not_crash_an_importer_that_handles_bad_workbooks():
    script="""
from concrete_pmm_pro.ui.csi_component_equilibrium import render_component_equilibrium
class File:
    name='broken.xlsx'
    def getvalue(self): return b'PKbroken'
render_component_equilibrium([File()],source_mode='unverified',concurrency_confirmed=False,evidence='',key_prefix='bad')
"""
    with patch('concrete_pmm_pro.ui.csi_component_equilibrium._read_audit',side_effect=BadZipFile('broken workbook')):
        at=AppTest.from_string(script).run(timeout=30)
    assert not at.exception and not at.dataframe
