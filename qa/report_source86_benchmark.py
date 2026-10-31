"""Isolated source-signature benchmark; never calls a solver or renderer.

Run the same script from the baseline and candidate PYTHONPATH. The synthetic
shell source mirrors a dataclass carrying full DataFrames. It is a stress
fixture, not the user's unavailable project or an engineering calculation.
"""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import pickle
import resource
import time

import numpy as np
import pandas as pd
from concrete_pmm_pro.reporting.bg40_data import source_signature


@dataclass
class ShellStressFixture:
    tables: dict


parser=argparse.ArgumentParser()
parser.add_argument('--state',required=True,type=Path)
parser.add_argument('--out',required=True,type=Path)
parser.add_argument('--rows',default=100000,type=int)
parser.add_argument('--columns',default=32,type=int)
args=parser.parse_args()
with args.state.open('rb') as source:
    state,report=pickle.load(source)
# The two tables deliberately share storage, as runtime stages often do.
frame=pd.DataFrame({f'Column {i}':np.arange(args.rows,dtype=float)+i/7.
                    for i in range(args.columns)})
state['slab_shell55_source_stress86']=ShellStressFixture({'native':frame,'review':frame})
before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
start=time.perf_counter()
signature=source_signature(state,report.metadata)
elapsed=time.perf_counter()-start
result={'rows_per_table':args.rows,'columns':args.columns,'tables':2,
    'serialized_cells':args.rows*args.columns*2,'signature':signature,
    'seconds':round(elapsed,3),'peak_rss_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
    'pre_hash_peak_rss_mib':round(before,2),
    'scope':'Isolated source fingerprint, not full report time. Synthetic source; all cells retained.'}
args.out.parent.mkdir(parents=True,exist_ok=True)
args.out.write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
