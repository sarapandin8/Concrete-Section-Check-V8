"""V+T rejects unverified vectors before solver execution."""
import json, math
from pathlib import Path
import pandas as pd
import pytest
from concrete_pmm_pro.ui import igird_combined_vt as vt, analysis_page as ap
from concrete_pmm_pro.io.girder_csi_import import SOURCE_TAG
from concrete_pmm_pro.ui.igird_case_review import controlling_result

def row(info=None,case='U2A',x=2.):
    return {'Case Name':case,'Station x (m)':x,'Mux':100.,'Nu':0.,'Vuy':800.,'Tu':300.,'Muy':0.,'Vux':0.,'Note':SOURCE_TAG+json.dumps(info) if info is not None else ''}
def confirmed(mode='correspondence',step='Max'):
    return dict(kind='CONCURRENT',concurrency_confirmed=True,evidence='Verified CSI correspondence export',source_mode=mode,step=step)
@pytest.mark.parametrize('info',[None,{}, {'kind':'ENVELOPE'}, {**confirmed(),'concurrency_confirmed':False},{**confirmed(),'evidence':''},confirmed('static','Max'),confirmed('unverified'),{**confirmed(),'kind':'ENVELOPE'}])
def test_reject_before_solver(monkeypatch,info):
    def forbidden(*a,**k): raise AssertionError('Unverified source reached solver/preparation')
    monkeypatch.setattr(vt,'_check_row',forbidden)
    monkeypatch.setattr(ap,'_beam_uls_combined_vt_demand_rows',forbidden)
    result=vt.check_dataframe({},pd.DataFrame([row(info)]),strength_route=None)
    assert result.Status.tolist()==['SOURCE BLOCKED']
    assert result['Overall D/C value'].isna().all()
    assert result['Calculation status'].eq('NOT CALCULATED').all()
    control=controlling_result(result,'Shear + Torsion')
    assert math.isnan(control['ratio']) and control['failed_rows']==0 and control['review_rows']==1
    assert ap._beam_uls_governing_combined_vt_row(result)['Status']=='SOURCE BLOCKED'
    assert not ap._beam_uls_combined_vt_has_finite_utilization(result)
    assert not vt.source_readiness_dataframe(result).empty
@pytest.mark.parametrize('info',[confirmed(),confirmed('static','')])
def test_verified_vectors_preserved_and_not_interpolated(monkeypatch,info):
    frame=pd.DataFrame([row(info,x=2.),row(info,x=3.),row({'kind':'ENVELOPE'},case='Other')])
    original=frame.copy(deep=True);calls=[]
    def check(state,source,**kw):
        calls.append(source.copy())
        return {'Case':source['Case Name'],'Governing x':f"{source['Station x (m)']:.3f} m",'Status':'PASS','Overall D/C value':.4,'Station type':'LOAD STATION'}
    monkeypatch.setattr(vt,'_check_row',check)
    result=vt.check_dataframe({},frame,strength_route=None)
    assert len(calls)==2 and len(result)==3
    assert [r['Station x (m)'] for r in calls]==[2.,3.]
    assert all(r['Vuy']==800. and r['Tu']==300. for r in calls)
    assert result.Status.tolist()==['SOURCE BLOCKED','PASS','PASS']
    assert ap._beam_uls_governing_combined_vt_row(result)['Status']=='SOURCE BLOCKED'
    pd.testing.assert_frame_equal(frame,original)
def test_native_640_rows_blocked_without_solver(monkeypatch):
    from concrete_pmm_pro.io.girder_csi_import import read_tables,prepare_csi_table,split_member_tables
    file=Path(__file__).resolve().parents[1]/'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx'
    table=read_tables(file.read_bytes(),file.name)['Bridge Object Girder Forces']
    def forbidden(*a,**k): raise AssertionError('Envelope reached solver')
    monkeypatch.setattr(vt,'_check_row',forbidden);count=0
    for group in split_member_tables(table,sheet_name='Bridge Object Girder Forces'):
        source=prepare_csi_table(group.frame,sheet_name='Bridge Object Girder Forces').frame
        result=vt.check_dataframe({},source,strength_route=None)
        assert len(result)==len(source) and result.Status.eq('SOURCE BLOCKED').all()
        assert result['Overall D/C value'].isna().all()
        count+=len(result)
    assert count==640
def test_result_version_invalidates_prior_results():
    assert ap._IGIRDER_COMBINED_VT_RESULT_VERSION==vt.RESULT_VERSION
    assert 'VTCONCURRENT19' in vt.RESULT_VERSION


def test_summary_blocked_has_no_engineering_failure_or_ratio():
    import app
    result=vt.check_dataframe({},pd.DataFrame([row({'kind':'ENVELOPE'})]),strength_route=None)
    entry={'result_version':vt.RESULT_VERSION,'combined_vt_df':result}
    selected=app._results_beam_uls_best_row(entry,'Shear + Torsion')
    assert selected['Status']=='SOURCE BLOCKED'
    assert app._results_beam_uls_utilization('Shear + Torsion',selected)=='-'
    assert 'simultaneous' in app._results_beam_uls_action('Shear + Torsion','SOURCE BLOCKED',selected)
    rows=app._results_igird_uls_summary_rows({}, {'Shear + Torsion':entry})
    assert rows[-1]['Status']=='SOURCE BLOCKED'
