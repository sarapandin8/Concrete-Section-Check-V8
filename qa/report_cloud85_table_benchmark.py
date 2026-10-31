"""Compare full-source Word assembly; no rows removed and no chart work."""
from argparse import ArgumentParser
from io import BytesIO
import json
from pathlib import Path
import resource
import time
import pandas as pd
from concrete_pmm_pro.reporting import bg40_word as word,bg40_template as reference

parser=ArgumentParser();parser.add_argument('--out',type=Path,required=True);parser.add_argument('--rows',type=int,default=15000)
args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
data=pd.DataFrame({'Case':[f'ULS-{i:06d}' for i in range(args.rows)],
    'Station x (m)':[i*.1 for i in range(args.rows)],'Mu (kN-m)':[i+.12345678901234 for i in range(args.rows)],
    'Vu (kN)':[i-.98765432101234 for i in range(args.rows)],'Tu (kN-m)':[i*.01234567890123 for i in range(args.rows)],
    'D/C':[.123456789012345]*args.rows,'Status':['FAIL']*args.rows})
document=reference.document();start=time.perf_counter()
try:
    from concrete_pmm_pro.reporting.word_stream import StreamingWordBody
except ImportError:
    word._table(document,data,'Full source benchmark','Same physical source rows; no trimming')
    output=BytesIO();document.save(output);result=output.getvalue();mode='EXPORT84 DOM'
else:
    with StreamingWordBody(document) as body:
        word._table(document,data,'Full source benchmark','Same physical source rows; no trimming')
        result=body.save()
    mode='CLOUD85 stream'
metadata={'mode':mode,'rows':args.rows,'columns':len(data.columns),'seconds':round(time.perf_counter()-start,3),
    'parent_peak_rss_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
    'output_bytes':len(result),'measurement_scope':'One Python process, native chart renderer not used; validation parse runs separately.'}
(args.out/'table.docx').write_bytes(result)
(args.out/'measurement.json').write_text(json.dumps(metadata,indent=2))
print(json.dumps(metadata),flush=True)
