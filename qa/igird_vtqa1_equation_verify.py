"""Independent US-unit substitution into stored production V/T equation traces.
Uses no solver/code-check helpers. All model modifications are explicitly QA.
"""
import hashlib,json,math,os
from pathlib import Path
import pandas as pd
REPO=Path(os.environ.get('CSP_QA_REPO',Path(__file__).resolve().parents[1]))
OUT=Path(os.environ.get('CSP_QA_OUT',REPO/'qa/evidence/igird_vtqa1'))
ksi=6.894757293168; inch=25.4; kip=4448.2216152605
comparisons=[]
def compare(kind,r,label,actual,expected):
    actual=float(actual);expected=float(expected)
    assert math.isfinite(actual) and math.isfinite(expected),(kind,label,actual,expected)
    abs_error=abs(actual-expected);rel_error=abs_error/max(abs(expected),1e-12)
    assert math.isclose(actual,expected,rel_tol=2e-9,abs_tol=1e-8),(kind,label,actual,expected)
    comparisons.append({'check':kind,'case':r['Case'],'x':r['Governing x'],'equation_quantity':label,
        'stored':actual,'independent':expected,'abs_error':abs_error,'rel_error':rel_error})
def parameters(r):
    eps=max(0,min(.006,float(r['εs raw'])))
    return 4.8/(1+750*eps),29+3500*eps
s=pd.read_csv(OUT/'shear_check_df.csv')
t=pd.read_csv(OUT/'torsion_check_df.csv')
c=pd.read_csv(OUT/'combined_vt_df.csv')
for _,r in s.loc[s['φVn kN'].notna()].iterrows():
    beta,theta=parameters(r);cot=1/math.tan(math.radians(theta))
    fc=r["f'c MPa"]/ksi;bw=r['bw mm']/inch;dv=r['dv mm']/inch
    vc=.0316*beta*math.sqrt(fc)*bw*dv*kip/1000
    vs=(r['Av/s mm2/m']/1000/inch)*(r['fy MPa']/ksi)*dv*cot*kip/1000
    limit=.25*fc*bw*dv*kip/1000
    compare('Shear',r,'beta',r['β'],beta);compare('Shear',r,'theta deg',r['θ deg'],theta)
    compare('Shear',r,'Vc kN',r['φVc kN']/r['φ'],vc)
    compare('Shear',r,'Vs kN',r['φVs kN']/r['φ'],vs)
    compare('Shear',r,'phiVn kN',r['φVn kN'],r['φ']*min(vc+vs,limit))
for _,r in t.loc[t['φTn kN-m'].notna()].iterrows():
    beta,theta=parameters(r);cot=1/math.tan(math.radians(theta))
    tn=2*(r['Ao mm2']/inch**2)*(r['At/s mm2/mm']/inch)*(r['fy MPa']/ksi)*cot*kip*inch/1e6
    equivalent=.9*r['ph mm']*abs(r['Demand kN-m'])*1e6/(2*r['Ao mm2'])/1000
    veff=math.hypot(abs(r['Vuy kN']),equivalent)
    fc_ksi=r["f'c MPa"]/ksi
    tcr=.126*math.sqrt(fc_ksi)*(r['Acp mm2']/inch**2)**2/(r['Pcp mm']/inch)*r['K']*kip*inch/1e6
    compare('Torsion',r,'theta deg',r['θ deg'],theta)
    compare('Torsion',r,'phiTn kN-m',r['φTn kN-m'],r['φ']*tn)
    compare('Torsion',r,'Veff kN',r['Veff kN'],veff)
    compare('Torsion',r,'phiTcr kN-m',r['φTcr kN-m'],r['φ']*tcr)
    compare('Torsion',r,'Investigation threshold kN-m',r['Threshold kN-m'],.25*r['φ']*tcr)
for _,r in c.loc[c['Overall D/C value'].notna()].iterrows():
    beta,theta=parameters(r);cot=1/math.tan(math.radians(theta))
    phi=r['φ'];fy=r['fy MPa'];dv=r['dv mm'];bv=r['bw mm'];fc=r["f'c MPa"]
    torsion=abs(r['Tu kN-m'])*1e6 if r['Threshold status']=='DESIGN REQUIRED' else 0
    at=torsion/(phi*2*r['Ao mm2']*fy*cot) if torsion else 0
    vc=.0316*beta*math.sqrt(fc/ksi)*(bv/inch)*(dv/inch)*kip
    shear=max(0,(abs(r['Vu kN'])*1000/phi-vc)/(fy*dv*cot))
    avmin=.0316*math.sqrt(fc/ksi)*(bv/inch)/(fy/ksi)*inch
    provided=r['Provided transverse mm2/mm']
    total=max(shear,avmin)+2*at
    available=max(0,provided-2*at)
    vs_nominal=available*fy*dv*cot
    vs_used=min(vs_nominal,abs(r['Vu kN'])*1000/phi)
    shear_force=abs(r['Vu kN'])*1000/phi-.5*vs_used
    torsion_force=.45*r['ph mm']*torsion/(2*r['Ao mm2']*phi) if torsion else 0
    required=max(0,abs(r['Mu kN-m'])*1e6/(phi*dv)-.5*r['Nu app kN']*1000/phi+cot*math.hypot(shear_force,torsion_force))
    resistance=r['As developed tension mm2']*fy+r['Aps developed tension mm2']*r['fps nominal min MPa']
    veff=math.hypot(abs(r['Vu kN'])*1000,.9*r['ph mm']*torsion/(2*r['Ao mm2'])) if torsion else abs(r['Vu kN'])*1000
    for label,actual,expected in [('beta',r['β'],beta),('theta deg',r['θ deg'],theta),
        ('Vc kN',r['Vc kN'],vc/1000),('At torsion mm2/mm',r['At torsion req mm2/mm'],at),
        ('Combined transverse mm2/mm',r['Combined transverse req mm2/mm'],total),
        ('Vs allocated kN',r['Vs allocated kN'],vs_nominal/1000),('Vs used kN',r['Vs used kN'],vs_used/1000),
        ('Longitudinal required kN',r['Longitudinal required kN'],required/1000),
        ('Longitudinal resistance kN',r['Longitudinal resistance kN'],resistance/1000),
        ('Transverse D/C',r['Transverse D/C value'],total/provided),
        ('Longitudinal D/C',r['Longitudinal D/C value'],required/resistance),
        ('Conservative Veff D/C',r['Stress D/C value'],veff/(phi*.25*fc*bv*dv))]: compare('Combined',r,label,actual,expected)
frame=pd.DataFrame(comparisons);frame.to_csv(OUT/'independent_equation_substitution.csv',index=False)
result={'status':'PASS','method':'Independent US-customary equations converted with ksi, inch, kip constants; no production equation helpers',
    'scalar_comparisons':len(frame),'max_relative_error':float(frame['rel_error'].max()),'max_absolute_error':float(frame['abs_error'].max()),
    'rows_checked':{'shear':int(s['φVn kN'].notna().sum()),'torsion':int(t['φTn kN-m'].notna().sum()),'combined':int(c['Overall D/C value'].notna().sum())},
    'scope':'Normal-weight solid precast I-girder, straight pretensioned strands, source-qualified hoops; hypothetical verified bar properties/development only',
    'code':'AASHTO LRFD 9th (2020): 5.7.2.1; 5.7.3.3; 5.7.3.4.2; 5.7.3.6.1/.2/.3'}
(OUT/'equation_verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
