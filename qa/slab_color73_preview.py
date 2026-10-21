"""Recolour verified native slab figures without repeating a structural solve.

The source files are captured PRINT72 Plotly figures. Check every non-colour
field, numeric colour-axis value and geometry before exporting new previews.
"""
from pathlib import Path
import argparse
import ast
from copy import deepcopy
import hashlib
import json
import math

import plotly.graph_objects as go
from plotly.colors import sample_colorscale


OLD = {'SAFE_FILL':'#e7f2f6','MID_FILL':'#b8d5df','LIMIT_FILL':'#f3e4bc',
    'FAIL_FILL':'#efc7c2','HIGH_FILL':'#d58b91','RESPONSE':'#5e889c','FAIL':'#b1535d'}


def palette():
    path=Path(__file__).resolve().parents[1]/'concrete_pmm_pro/visualization/slab_print72.py'
    values={}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in OLD:
            values[node.targets[0].id]=ast.literal_eval(node.value)
    assert values.keys()==OLD.keys()
    return values


def without_colours(value):
    if isinstance(value,dict):
        return {k:without_colours(v) for k,v in value.items() if k not in {'color','fillcolor','colorscale'}}
    if isinstance(value,list):return [without_colours(v) for v in value]
    return value


def recolour(source,new_palette):
    result=deepcopy(source)
    mapping={OLD[name]:new_palette[name] for name in OLD}
    def replace(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in {'color','fillcolor'} and isinstance(item,str):value[key]=mapping.get(item,item)
                elif key=='colorscale' and isinstance(item,list):value[key]=[[stop,mapping.get(colour,colour)] for stop,colour in item]
                else:replace(item)
        elif isinstance(value,list):
            for item in value:replace(item)
    replace(result)
    scale=next((trace for trace in source['data'] if trace.get('name')=='D/C scale'),None)
    if scale:
        top=scale['marker']['cmax'];old_scale=scale['marker']['colorscale']
        new_scale=[[position,mapping.get(colour,colour)] for position,colour in old_scale]
        fills={}
        for index in range(32):
            centre=((index+.5)/16*math.log(2) if index<16 else
                math.log(2)+(index-16+.5)/16*(top-math.log(2)))
            fills[sample_colorscale(old_scale,[centre/top])[0]]=sample_colorscale(new_scale,[centre/top])[0]
        for before,after in zip(source['data'],result['data']):
            if before.get('name')=='Element envelope':
                assert before['fillcolor'] in fills
                after['fillcolor']=fills[before['fillcolor']]
    assert without_colours(source)==without_colours(result)
    for before,after in zip(source['data'],result['data']):
        a,b=before.get('marker',{}),after.get('marker',{})
        if isinstance(a.get('color'),list):assert a['color']==b['color']
        if 'colorscale' in a:assert [x[0] for x in a['colorscale']]==[x[0] for x in b['colorscale']]
    return result


def run(source,output):
    output.mkdir(parents=True,exist_ok=True)
    current=palette();charts=json.loads((source/'manifest.json').read_text());checks=[]
    for chart in charts:
        before=json.loads((source/chart['file']).read_text())
        after=recolour(before,current)
        go.Figure(after).write_json(output/chart['file'])
        stem=Path(chart['file']).stem
        go.Figure(after).write_image(output/(stem+'.png'),width=1440,height=780,scale=1)
        clean=json.dumps(without_colours(after),sort_keys=True,separators=(',',':')).encode()
        checks.append({'view':chart['view'],'mode':chart['mode'],'non_colour_fields_unchanged':True,
            'numeric_colour_values_unchanged':True,'non_colour_sha256':hashlib.sha256(clean).hexdigest()})
        if chart['view']=='Direct N–M · transverse' and chart['mode']=='plan':
            go.Figure(after).write_image(output/'Slab_COLOR73_Girders_Bearings.png',width=1440,height=780,scale=1)
    evidence={'milestone':'SLAB.COLOR73','source':'Verified PRINT72 native-data Plotly figures',
        'structural_solver_rerun':False,'palette':current,'figures_verified':len(checks),
        'all_non_colour_fields_unchanged':True,'checks':checks}
    (output/'Colour_Verification.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps({k:v for k,v in evidence.items() if k!='checks'},indent=2),flush=True)
    return evidence


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.source,args.output)
