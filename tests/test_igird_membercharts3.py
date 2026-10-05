import copy
import pandas as pd
import pytest
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.igird_member_results import member_inputs, calculate_member, result_hash, current_result, titled_figure, make_member_flexure_figure
from concrete_pmm_pro.ui.igird_vt_workspace import make_overview_figure
from test_igird_uls6_torsion_general_procedure import _state, _route, _demand


def model():
    state=_state()
    state['section_parameters']={'composite_enabled':True,'B1_mm':800.,'Be_mm':2400.,'Tslab_mm':220.,'deck_fc_MPa':35.,'Be_mode':'Manual','Be_strength_verified':True}
    frames=[]
    for member,factor in [('Exterior Girder',1),('Interior Girder 2',1.3)]:
        for case in ('ULS1','ULS2'):
            for x in (2.,10.,18.):
                row=_demand(x=x,tu=100*factor,vu=200*factor,mux=500*factor).iloc[0].to_dict()
                row['Note']=''
                row['Case Name']=member+' / '+case
                row['Girder']=member
                frames.append(row)
    state[BANK_KEY]=pd.DataFrame(frames)
    return state


def test_each_member_retains_all_cases_and_filters_inactive():
    state=model();state[BANK_KEY].loc[0,'Active']=False
    rows=member_inputs(state)
    assert len(rows['Exterior Girder'])==5
    assert len(rows['Interior Girder 2'])==6
    for name,frame in rows.items():
        assert frame['Case Name'].str.startswith(name+' / ').all()
        assert frame['Case Name'].nunique()==2


@pytest.mark.parametrize('check,key',[('Flexure','flexure_preview_df'),('Shear','shear_check_df'),('Torsion','torsion_check_df'),('Shear + Torsion','combined_vt_df')])
def test_real_solvers_use_independent_member_rows_and_same_accepted_engine(check,key):
    state=model();before=copy.deepcopy(state)
    rows=member_inputs(state)
    for member,frame in rows.items():
        result=calculate_member(state,frame,check_name=check,route=_route())
        assert 'error' not in result,result
        output=result[key]
        assert not output.empty
        assert output['Case'].dropna().astype(str).str.startswith(member+' / ').all()
        if check!='Flexure':
            direct=ap._beam_uls_calculate_selected_check(state,frame,selected_check=check,strength_route=_route())
            pd.testing.assert_frame_equal(output,direct[key])
    pd.testing.assert_frame_equal(state[BANK_KEY],before[BANK_KEY])
    assert state['section_geometry'].model_dump()==before['section_geometry'].model_dump()


@pytest.mark.parametrize('check',['Flexure','Shear','Torsion','Shear + Torsion'])
def test_stale_is_scoped_to_member_loads_and_shared_model(check):
    state=model();rows=member_inputs(state)
    hashes={n:result_hash(state,f,check_name=check,route=_route()) for n,f in rows.items()}
    cache={n:{check:{'input_hash':h,'result':{'owner':n}}} for n,h in hashes.items()}
    for n in rows:assert current_result(cache,n,check,hashes[n])=={'owner':n}
    changed=rows['Exterior Girder'].copy();changed.loc[changed.index[0],'Mux']=777
    h=result_hash(state,changed,check_name=check,route=_route())
    assert current_result(cache,'Exterior Girder',check,h) is None
    assert current_result(cache,'Interior Girder 2',check,hashes['Interior Girder 2'])=={'owner':'Interior Girder 2'}
    state['section_parameters']['Tslab_mm']=250
    for n,f in rows.items():
        assert current_result(cache,n,check,result_hash(state,f,check_name=check,route=_route())) is None


def test_figure_title_and_demand_identity_are_separate():
    state=model();rows=member_inputs(state)
    for n,f in rows.items():
        result=calculate_member(state,f,check_name='Flexure',route=_route())
        fig=make_member_flexure_figure(state,f,result['flexure_preview_df'],code_label='AASHTO',member=n)
        assert tuple(fig.layout.xaxis.range)==(0,20)
        assert sum(t.name=='φMn' and t.showlegend is not False for t in fig.data)==1
        assert fig.layout.title.text.startswith('Girder: '+n)
        assert all(other not in fig.to_json() for other in rows if other!=n)
