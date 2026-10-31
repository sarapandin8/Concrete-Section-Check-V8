"""Run the unchanged native renderer/UI harness for the source-memory patch."""
from pathlib import Path
import json
import runpy
import sys

root=Path(__file__).resolve().parents[1]
runpy.run_path(str(root/'qa/report_cloud85_ui_export.py'),run_name='__main__')
out=Path(sys.argv[sys.argv.index('--out')+1])
result=json.loads((out/'Cloud85_Export_Validation.json').read_text())
result['cloud86']=result.pop('cloud85')
assert result['cloud86']['diagnostics']['environment']['release']=='REPORT.CLOUD86'
(out/'Cloud86_Export_Validation.json').write_text(json.dumps(result,indent=2))
