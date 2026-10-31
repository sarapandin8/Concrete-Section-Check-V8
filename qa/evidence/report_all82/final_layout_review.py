from pathlib import Path
from hashlib import sha256
import json
import fitz
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent
NAMES=['i_girder','column','building_beam','bridge_beam','railway_u','crossbeam_cip','crossbeam_segmental']
for name in NAMES:
 folder=ROOT/'render'/name
 if not (folder/'CSP82_Default_Report_From_App.pdf').exists():
  print(name,'not rendered yet',flush=True);continue
 doc=fitz.open(folder/'CSP82_Default_Report_From_App.pdf')
 pages=sorted(folder.glob('page-*.png'),key=lambda p:int(p.stem.split('-')[-1]))
 assert len(pages)==len(doc),(name,len(pages),len(doc))
 outside=[];blank=[];sparse=[]
 for i,page in enumerate(doc):
  body=''.join(b[4] for b in page.get_text('blocks') if len(b)>6 and b[6]==0 and b[1]>60)
  images=page.get_image_info()
  if len(body.strip())<12 and not images:blank.append(i+1)
  if len(body.strip())<100 and not images:sparse.append({'page':i+1,'body':body.strip()})
  for block in page.get_text('dict')['blocks']:
   for line in block.get('lines',[]):
    for span in line['spans']:
     x0,y0,x1,y1=span['bbox']
     if x0<-.5 or y0<-.5 or x1>page.rect.width+.5 or y1>page.rect.height+.5:
      outside.append({'page':i+1,'text':span['text'],'bbox':span['bbox']})
 result={'pages':len(doc),'outside_page_text':outside,'possible_blank_pages':blank,'sparse_pages_for_review':sparse,
  'document_sha256':sha256((ROOT/'exports'/name/'CSP82_Default_Report_From_App.docx').read_bytes()).hexdigest(),
  'pixel_hashes':{p.name:sha256(p.read_bytes()).hexdigest() for p in pages}}
 (folder/'Layout_Check.json').write_text(json.dumps(result,indent=2))
 old=ROOT/'render'/(name+('_before_endpoint_fix' if name.startswith('crossbeam') else '_before_caption_fix'))
 if name=='i_girder':old=ROOT.parents[1]/'report_default81/verification/delivery_render'
 changed=[i+1 for i,p in enumerate(pages) if not (old/p.name).exists() or sha256(p.read_bytes()).digest()!=sha256((old/p.name).read_bytes()).digest()]
 change={'pages':len(doc),'changed_pages':changed,'comparison':str(old)}
 (folder/'Render_Changes.json').write_text(json.dumps(change,indent=2))
 out=ROOT/'delivery_review'/name;out.mkdir(parents=True,exist_ok=True)
 for oldsheet in out.glob('sheet-*.png'):oldsheet.unlink()
 for offset in range(0,len(pages),4):
  batch=pages[offset:offset+4];w=max(Image.open(p).width for p in batch);h=max(Image.open(p).height for p in batch);label=30
  canvas=Image.new('RGB',(2*w,2*(h+label)),(235,235,235));draw=ImageDraw.Draw(canvas)
  for j,p in enumerate(batch):
   x=(j%2)*w;y=(j//2)*(h+label)
   draw.text((x+8,y+8),name+' '+p.stem,fill=(0,0,0))
   with Image.open(p) as img:canvas.paste(img,(x,y+label))
  canvas.save(out/f'sheet-{offset//4+1}.png')
 print(name,'pages',len(doc),'changed',changed,'outside',len(outside),'blank',blank,'sparse',sparse,flush=True)
