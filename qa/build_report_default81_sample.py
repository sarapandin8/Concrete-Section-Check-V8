from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import json
import pickle
import time
from io import BytesIO
import math
import openpyxl

from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json
from concrete_pmm_pro.io.girder_load_bank import activate_member
from concrete_pmm_pro.io.girder_csi_import import tag_app_source
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr, igird_sls53_results as sls
from concrete_pmm_pro.ui.igird_case_review import FRAME_KEYS
from concrete_pmm_pro.io import girder_deflect70 as deflect_import, slab_shell_import
from concrete_pmm_pro.serviceability import girder_deflect70 as deflect
from concrete_pmm_pro.analysis import slab_review68 as slab
from concrete_pmm_pro.reporting.bg40_data import build_calculation_report
from concrete_pmm_pro.reporting.report_models import ReportMetadata
from test_igird_casecontrol5 import review_model
from test_slab_punch76_auto import state as slab_seed
from test_slab_punching64 import area
from test_slab_connections59 import connected_state

import argparse
parser=argparse.ArgumentParser(description='Build the hypothetical report QA state using the actual analysis engines')
parser.add_argument('--out',type=Path,required=True)
OUT=parser.parse_args().out
OUT.mkdir(exist_ok=True)
started=time.monotonic()
state={}
apply_project_to_session_state(project_from_json(Path('qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()),state)
# Reuse the prescribed simultaneous demand vectors only. Keep the actual
# 12-vertex I-section, physical rebars, strands and settings from the example
# project; the isolated rectangular unit-test geometry is not a bridge model.
state['igird_uls_member_bank']=deepcopy(review_model()['igird_uls_member_bank'])
state['project_name']='SAMPLE 20 m I Girder and Slab Checks'
state['igird_uls_member_bank']=tag_app_source(state['igird_uls_member_bank'],source_name='Hypothetical static demonstration vectors',sheet_name='SAMPLE',source_mode='static',concurrency_confirmed=True,evidence='Prescribed simultaneous static vectors for demonstration only')
activate_member(state,'Exterior Girder')

# A distinct imported two-metre slab patch demonstrates this module's scope.
deck=slab_seed(areas=[area(x=.5,y=.5,l=200,b=200,vu=10,name='SAMPLE P1')])
package=deck[slab_shell_import.BANK_KEY]
package.tables['frames']=deepcopy(connected_state()[slab_shell_import.BANK_KEY].tables['frames'])
package.units['frames']={'Frame':'Text','JointI':'Text','JointJ':'Text','IsCurved':'Yes/No'}
# Reimport the complete sample workbook so its recorded source digest matches
# the actual tables, including native girder connectivity.
book=openpyxl.Workbook()
book.remove(book.active)
for spec in (*slab_shell_import.SPECS,*slab_shell_import.OPTIONAL_SPECS):
    frame=package.tables.get(spec.key)
    if frame is None or frame.empty:
        continue
    sheet=book.create_sheet(spec.key)
    sheet.append(['TABLE:  '+spec.title])
    cols=list(frame.columns)
    sheet.append(cols)
    sheet.append([package.units.get(spec.key,{}).get(c,'Text') for c in cols])
    for values in frame.itertuples(index=False,name=None):
        sheet.append([v.item() if hasattr(v,'item') else (None if isinstance(v,float) and math.isnan(v) else v) for v in values])
slab_bytes=BytesIO()
book.save(slab_bytes)
(OUT/'SAMPLE_Slab_Source.xlsx').write_bytes(slab_bytes.getvalue())
slab_bytes.name='SAMPLE_Slab_Source.xlsx'
state[slab_shell_import.BANK_KEY]=slab_shell_import.parse_files([slab_bytes])
assert state[slab_shell_import.BANK_KEY].ready,state[slab_shell_import.BANK_KEY].errors
state['project_metadata']={**dict(state.get('project_metadata') or {}),**deepcopy(deck.get('project_metadata') or {})}
state['beam_girder_interface_shear_settings']=deepcopy(deck['beam_girder_interface_shear_settings'])

print('Calculating actual SLS stress engine',flush=True)
with patch.object(ap.st,'session_state',state):
    sls_result=sls.calculate()
    span,_,bases=sls.prepare()
    generated=ap._girder_deflection_curve_rows(basis_options=bases)
print('SLS',[(s['Stage'],s['Status']) for s in sls_result['summary']],flush=True)

print('Calculating actual deflection engine and importing sample workbook',flush=True)
state[deflect_import.BANK_KEY]=deflect_import.parse_workbook(Path('tests/fixtures/sls_deflect70/SLS_deflection_source.xlsx').read_bytes(),'SAMPLE SLS deflection source.xlsx')
state[deflect.SETTINGS_KEY]={'profile':'rail_project'}
state[deflect.RESULT_KEY]=deflect.calculate(state,generated,span)

print('Calculating actual slab engine',flush=True)
state[slab.RESULT_KEY]=slab.calculate(state)
print('Slab',state[slab.RESULT_KEY]['status'],flush=True)

print('Calculating actual ULS engines',flush=True)
route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
state[mr.CACHE_KEY]={}
for member,rows in mr.member_inputs(state).items():
    state[mr.CACHE_KEY][member]={}
    for check in FRAME_KEYS:
        print(member,check,flush=True)
        result=mr.calculate_member(state,rows,check_name=check,route=route)
        if result.get('error'):
            raise RuntimeError(result)
        state[mr.CACHE_KEY][member][check]={'input_hash':mr.result_hash(state,rows,check_name=check,route=route),'result':result}

meta=ReportMetadata(report_title='SAMPLE I Girder Calculation Report',project_name=state['project_name'],prepared_by='Concrete Section Pro demonstration',checked_by='Not checked for project issue',revision='SAMPLE',report_date='30 October 2026',note='DEMONSTRATION ONLY. Hypothetical input vectors and bundled sample workbooks are used to illustrate the actual application output. This is not a design report for a real project. The 2 m slab patch in Chapter 10 is a separate module demonstration and is not the full-span deck model of the 20 m girder. All source FAIL, Preview and REVIEW states are retained.')
report=build_calculation_report(state,meta)
report.chapters[9].notes.insert(0,'SAMPLE MODULE SCOPE: This imported 2 m slab patch is an independent demonstration, not the full-span slab of the 20 m I-girder. Use its own source geometry and local thickness.')
with (OUT/'calculated_example.pkl').open('wb') as f:pickle.dump((state,report),f)
summary={'status':report.status,'chapters':[{'number':c.number,'title':c.title,'status':c.status,'calculations':len(c.calculations),'figures':len(c.figures)} for c in report.chapters],'controls':report.controls.to_dict('records'),'elapsed_seconds':time.monotonic()-started}
(OUT/'calculation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str))
print(json.dumps(summary,ensure_ascii=False,indent=2,default=str),flush=True)
