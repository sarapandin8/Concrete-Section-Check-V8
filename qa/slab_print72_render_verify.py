"""Render every native-data chart and check printed label / legend bounds."""
from pathlib import Path
import argparse
import base64
import json

from plotly.offline import get_plotlyjs
from playwright.sync_api import sync_playwright


def run(figures,output):
    output.mkdir(parents=True,exist_ok=True)
    charts=json.loads((figures/'manifest.json').read_text())
    evidence=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1440,'height':780},device_scale_factor=1)
        page.set_default_timeout(120000)
        page.set_content('<html><head><style>html,body{margin:0;background:white}#plot{width:1440px;height:780px}</style></head><body><div id="plot"></div></body></html>')
        page.add_script_tag(content=get_plotlyjs())
        for chart in charts:
            payload=json.loads((figures/chart['file']).read_text())
            facts=page.evaluate('''async fig=>{
              fig.layout.width=1440;fig.layout.height=780;
              await Plotly.react('plot',fig.data,fig.layout,{displayModeBar:false,staticPlot:true});
              const bounds=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,text:e.textContent}};
              return {annotations:[...document.querySelectorAll('#plot .annotation')].map(bounds),
                legend:document.querySelector('#plot .legend')?bounds(document.querySelector('#plot .legend')):null,
                colorbar:document.querySelector('#plot .colorbar')?bounds(document.querySelector('#plot .colorbar')):null,
                title:bounds(document.querySelector('#plot .gtitle')),
                meta:document.querySelector('#plot')._fullLayout.meta};
            }''',payload)
            assert facts['meta']['girder_count']==6 and facts['meta']['bearing_stations_m']==[.4,19.6]
            for box in [*facts['annotations'],facts['title'],*([facts['legend']] if facts['legend'] else []),*([facts['colorbar']] if facts['colorbar'] else [])]:
                assert box['x']>=-1 and box['y']>=-1 and box['x']+box['w']<=1441 and box['y']+box['h']<=781,(chart,box)
            def overlaps(a,b):
                return min(a['x']+a['w'],b['x']+b['w'])-max(a['x'],b['x'])>1 and min(a['y']+a['h'],b['y']+b['h'])-max(a['y'],b['y'])>1
            boxes=facts['annotations']
            for i,a in enumerate(boxes):
                assert not overlaps(a,facts['title']),(chart,'title',a)
                if facts['legend']:assert not overlaps(a,facts['legend']),(chart,'legend',a)
                if facts['colorbar']:assert not overlaps(a,facts['colorbar']),(chart,'colorbar',a)
                for b in boxes[i+1:]:assert not overlaps(a,b),(chart,a,b)
            stem=Path(chart['file']).stem
            page.screenshot(path=str(output/(stem+'.png')),animations='disabled')
            if chart['view']=='Direct N–M · transverse' and chart['mode']=='plan':
                data=page.evaluate("async()=>await Plotly.toImage(document.querySelector('#plot'),{format:'svg',width:1440,height:780})")
                from urllib.parse import unquote
                if data.startswith('data:image/svg+xml;base64,'):
                    content=base64.b64decode(data.split(',',1)[1])
                else:content=unquote(data.split(',',1)[1]).encode()
                (output/'Top_Slab_Girder_Bearing_Preview.svg').write_bytes(content)
            evidence.append({'view':chart['view'],'mode':chart['mode'],'annotation_count':len(boxes),
                'labels_within_export':True,'label_title_legend_overlap':False,'export_width':1440,'export_height':780})
        browser.close()
    result={'milestone':'SLAB.PRINT72','charts_checked':len(evidence),'checks':evidence}
    (output/'Render_Verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--figures',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.figures,args.output)
