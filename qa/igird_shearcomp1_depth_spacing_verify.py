"""Independent depth bounds, shear stress, spacing and epsilon substitutions.
No production solver or code-check functions are imported. Counts include the
actual unchanged-P source and the explicitly hypothetical P=0 UI test model.
"""
import json, math, os
from pathlib import Path
import pandas as pd
REPO=Path(os.environ.get('CSP_QA_REPO',Path(__file__).resolve().parents[1]))
OUT=Path(os.environ.get('CSP_QA_OUT',REPO/'qa/evidence/igird_shearcomp1'))
items=[]
def check(source,row,quantity,actual,expected):
    actual,expected=float(actual),float(expected)
    assert math.isfinite(actual) and math.isfinite(expected),(source,quantity,actual,expected)
    assert math.isclose(actual,expected,rel_tol=2e-9,abs_tol=1e-8),(source,row['Governing x'],quantity,actual,expected)
    items.append({'model':source,'case':row['Case'],'x':row['Governing x'],'quantity':quantity,
        'stored':actual,'independent':expected,'abs_error':abs(actual-expected)})
for stem in ('shear_check_df','actual_source_shear_check_df'):
    data=pd.read_csv(OUT/(stem+'.csv'))
    for _,r in data.loc[data['φVn kN'].notna()].iterrows():
        phi,fc,bv,dv=r['φ'],r["f'c MPa"],r['bw mm'],r['dv mm']
        vp=r['Vp kN']*1000
        stress=(abs(r['Demand kN'])*1000-phi*vp)/(phi*bv*dv)
        stress=max(0,stress)
        check(stem,r,'vu MPa',r['Shear stress MPa'],stress)
        check(stem,r,'vu/fc',r['Shear stress / fc'],stress/fc)
        limit=min(.8*dv,609.6) if stress/fc<.125 else min(.4*dv,304.8)
        check(stem,r,'smax mm',r['s max mm'],limit)
        lower=max(.9*r['de mm'],.72*r['h mm'])
        check(stem,r,'dv lower bound mm',r['dv lower bound mm'],lower)
        check(stem,r,'dv mm',dv,max(r['C-T lever arm mm'],lower))
        numerator=r['Mu used kN-m']*1e6/dv+.5*r['Nu AASHTO kN']*1000+abs(r['Demand kN'])*1000-vp-r['Aps fpo kN']*1000
        denominator=200000*r['As tension mm2']+195000*r['Aps developed tension mm2']
        check(stem,r,'epsilon numerator N',r['εs numerator N'],numerator)
        check(stem,r,'epsilon denominator N',r['εs denominator N'],denominator)
        epsilon=numerator/denominator
        if r['Nu AASHTO kN']>1e-12:epsilon*=2  # Existing conservative axial-tension policy.
        check(stem,r,'epsilon raw',r['εs raw'],epsilon)
frame=pd.DataFrame(items);frame.to_csv(OUT/'independent_depth_spacing_epsilon.csv',index=False)
result={'status':'PASS','scalar_comparisons':len(frame),'max_abs_error':float(frame['abs_error'].max()),
    'methods':['Direct AASHTO 5.7.2.8 depth bounds','vu=(|Vu|-phi*Vp)/(phi*bv*dv)','5.7.2.6 spacing threshold',
        'Direct 5.7.3.4.2 epsilon numerator/denominator; Es=200000 MPa and Ep=195000 MPa for this source'],
    'scope':'Stored force-resultant equilibrium and independently checked rectangular C/T/de analytic unit test; no independent general polygon solver claim.'}
(OUT/'depth_spacing_verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
