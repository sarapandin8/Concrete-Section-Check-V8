"""Measure actual Shear Calculate on identical original rows, not UI redraw."""
import argparse
import json
import logging
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
for name in ('streamlit','streamlit.runtime.scriptrunner_utils.script_run_context'):
    logging.getLogger(name).setLevel(logging.ERROR)
import pandas as pd
from scipy.optimize import linprog
from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state
from concrete_pmm_pro.ui import analysis_page as ap


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    raw=args.project.read_text();project=json.loads(raw)
    bank=pd.DataFrame(project['metadata']['workflow_load_tables']['igird_uls_member_bank'])
    rows=bank.iloc[4:36].copy()
    linprog([1.],bounds=[(0.,1.)],method='highs')
    times=[]
    for _ in range(2):
        state={};apply_project_to_session_state(project_from_json(raw),state)
        route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
        started=time.perf_counter()
        ap._beam_uls_calculate_selected_check(state,rows,selected_check='Shear',strength_route=route)
        times.append(time.perf_counter()-started)
    record={'rows':len(rows),'calculate_shear_seconds':times,'scope':'Warm LP; fresh state each run; code checks plus model'}
    args.output.write_text(json.dumps(record,indent=2)+'\n')
    print(record)


if __name__=='__main__':main()
