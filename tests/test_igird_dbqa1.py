from pathlib import Path
import json
import math
import pandas as pd
import pytest
from concrete_pmm_pro.validation.igird_debonding import igird_debonding_audit,debonding_status
from concrete_pmm_pro.ui import prestress_page as p
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json

ROOT=Path(__file__).resolve().parents[1]

def model():
    j=json.loads((ROOT/'qa/fixtures/I_Girder_20m.json').read_text())
    rows=j['metadata']['girder_strand_layout_table']
    points=[]
    for row in rows:
        if row['Active']:
            for n,x in enumerate(row['Strand x positions mm'].split(','),1):
                points.append({'Group ID':row['Group ID'],'Strand no.':n,'x_mm':float(x),'Diameter mm':12.7})
    return j,pd.DataFrame(rows),pd.DataFrame(points)

def audit(rows=None,points=None,span=20):
    j,r,ps=model()
    return igird_debonding_audit(r if rows is None else rows,span_length_m=span,section_parameters=j['section_parameters'],points=ps if points is None else points).set_index('Rule',drop=False)

def test_actual_model_exposes_real_detailing_violations_and_recommendation():
    a=audit()
    assert a.loc['Input layout','Status']=='OK'
    assert a.loc['Per-row debonded ratio — A','Status']=='OK'
    assert a.loc['Total debonded ratio — I trigger','Status']=='INFO'
    assert '15/34 = 44.1%' in a.loc['Total debonded ratio — I trigger','Demand / value']
    assert a.loc['Debond length recommendation — G','Status']=='REVIEW'
    assert '5.000' in a.loc['Debond length recommendation — G','Demand / value']
    assert a.loc['Web projection strands fully bonded — I','Status']=='FAIL'
    assert 'Row 1 #4 (x=-55 mm)' in a.loc['Web projection strands fully bonded — I','Demand / value']
    assert 'Row 4 #4 (x=0 mm)' in a.loc['Web projection strands fully bonded — I','Demand / value']
    assert a.loc['Outer-most flange strands bonded — I','Demand / value']=='Row 4 #1; Row 4 #7'
    assert a.loc['Alternating bonded/debonded positions — E','Status']=='FAIL'
    assert debonding_status(a)=='FAIL'

def test_shortening_only_row1_cannot_clear_unsafe_detailing():
    _,r,ps=model();r.loc[0,['Left debond m','Right debond m']]=4
    a=audit(r,ps)
    assert debonding_status(a)=='FAIL'
    assert a.loc['Strands terminating per section — B','Status']=='FAIL' # now 8 terminate at x=4
    assert 'x=4 m: 8 strands' in a.loc['Strands terminating per section — B','Demand / value']

def test_row_45_percent_boundary_uses_physical_y_not_group_count():
    _,r,ps=model()
    r.loc[0,'Debonded strand nos']='1,2,4,6,8'
    assert audit(r,ps).loc['Per-row debonded ratio — A','Status']=='FAIL'
    # Split one nine-strand physical row into two input groups; combined 4/9 passes.
    r.loc[0,'No. Strands']=5;r.loc[0,'Debonded strand nos']='2,4'
    extra=r.iloc[0].copy();extra['Group ID']='Split';extra['No. Strands']=4;extra['Debonded strand nos']='1,3'
    r=pd.concat([r,pd.DataFrame([extra])],ignore_index=True)
    ps.loc[(ps['Group ID']=='Row 1') & (ps['Strand no.']>5),'Group ID']='Split'
    ps.loc[ps['Group ID']=='Split','Strand no.']-=5
    assert audit(r,ps).loc['Per-row debonded ratio — A','Status']=='OK'

@pytest.mark.parametrize('value',[-1,math.nan,math.inf])
def test_invalid_sleeve_lengths_are_input_errors(value):
    _,r,ps=model();r.loc[0,'Left debond m']=value
    assert debonding_status(audit(r,ps))=='ERROR'

def test_no_bonded_zone_is_error_and_invalid_span_is_error():
    _,r,ps=model();r.loc[0,['Left debond m','Right debond m']]=10
    assert debonding_status(audit(r,ps))=='ERROR'
    assert debonding_status(audit(span=0))=='ERROR'

def test_spacing_uses_actual_strand_diameter_and_counts_individual_ends():
    _,r,ps=model();r.loc[0,['Left debond m','Right debond m']]=4.5
    a=audit(r,ps)
    assert a.loc['Termination spacing — C','Status']=='FAIL'
    assert '0.500' in a.loc['Termination spacing — C','Demand / value']
    ps['Diameter mm']=math.nan
    assert audit(r,ps).loc['Termination spacing — C','Status']=='REVIEW'

def test_asymmetric_coordinates_require_failed_pair_review():
    _,r,ps=model();ps.loc[(ps['Group ID']=='Row 1') & (ps['Strand no.']==2),'x_mm']=-160
    assert audit(r,ps).loc['Symmetric distribution and termination — D','Status']=='FAIL'

def test_no_sleeves_and_full_bonded_layout_does_not_fail_length():
    _,r,ps=model();r['Left debond m']=0;r['Right debond m']=0
    a=audit(r,ps)
    assert a.loc['Debond length recommendation — G','Status']=='NOT REQUIRED'
    assert not (a['Status']=='FAIL').any()

def test_ui_uses_aashto9_route_and_preserves_8th_edition_route(monkeypatch):
    j,_,_=model();s={};apply_project_to_session_state(project_from_json(json.dumps(j)),s)
    monkeypatch.setattr(p.st,'session_state',s)
    status,a,scoped=p._girder_debonding_qa(s['girder_strand_layout_table'],20,s['section_geometry'])
    assert scoped and status=='FAIL'
    s['project_code_edition']='AASHTO LRFD 8th Edition';s['code_edition']='AASHTO LRFD 8th Edition'
    status,a,scoped=p._girder_debonding_qa(s['girder_strand_layout_table'],20,s['section_geometry'])
    assert not scoped and status=='ERROR'
    assert 'Debond length' in a['Rule'].tolist()
