import sys
sys.path.insert(0,'tests')
from pathlib import Path
import plotly.io as pio
from test_igird_membercharts3 import model
from test_igird_uls6_torsion_general_procedure import _route
from concrete_pmm_pro.ui.igird_member_results import member_inputs,calculate_member,titled_figure,make_member_flexure_figure
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.igird_vt_workspace import make_overview_figure
state=model()
out=Path('qa/evidence/igird_membercharts3/figures');out.mkdir(exist_ok=True)
for check in ['Flexure','Shear','Torsion','Shear + Torsion']:
 for n,rows in member_inputs(state).items():
  result=calculate_member(state,rows,check_name=check,route=_route())
  if check=='Flexure':
   fig=make_member_flexure_figure(state,rows,result['flexure_preview_df'],member=n,code_label='AASHTO LRFD 9th Edition')
  else:
   key={'Shear':'shear_check_df','Torsion':'torsion_check_df','Shear + Torsion':'combined_vt_df'}[check]
   fig=make_overview_figure(rows,result[key],check_name=check,code_label='AASHTO LRFD 9th Edition',span_m=20.)
  if check!='Flexure':titled_figure(fig,n)
  fig.update_layout(width=1440,height=560,margin=dict(l=82,r=42,t=100,b=116),title_font=dict(size=18))
  file=out/(n.replace(' ','_')+'_'+check.replace(' ','_').replace('+','plus'))
  fig.write_image(str(file)+'.png')
print('Rendered all eight named member/check figures using real solver outputs.')
