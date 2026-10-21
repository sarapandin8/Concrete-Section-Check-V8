"""Run the Analysis regression set and isolate the legacy global Streamlit stub."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

PATTERNS = [
    'test_serviceability*.py', 'test_girder*.py', 'test_igird_sls*.py',
    'test_result_summary*.py', 'test_results*.py', 'test_report_qa*.py',
    'test_project*.py', 'test_slab*.py', 'test_igird_uls*.py', 'test_igird_shear*.py',
    'test_igird_flexure_development.py', 'test_igird_deckuls1.py', 'test_igird_code52.py',
    'test_analysis71.py', 'test_dirty_state.py', 'test_ui_active_tabs1_navigation.py',
    'test_workflow_status_alignment.py',
]
ISOLATED = 'tests/test_girder_strand_debonding_ui.py'


def run(output):
    root = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=True)
    files = sorted({str(p.relative_to(root)) for pattern in PATTERNS
                    for p in (root/'tests').glob(pattern)} - {ISOLATED})
    evidence = {'scope': 'Analysis and related source/summary/report regressions; not the entire repository',
        'isolated_reason': 'The legacy strand UI test module replaces sys.modules[streamlit] without restoration.',
        'main_files': len(files), 'runs': {}}
    for name, selected in [('main', files), ('isolated', [ISOLATED])]:
        xml = output/(name+'.xml')
        with (output/(name+'.log')).open('w') as log:
            code = subprocess.run([sys.executable, '-m', 'pytest', '-q', *selected,
                '--junitxml='+str(xml.resolve())], cwd=root, stdout=log, stderr=log).returncode
        suites = list(ET.parse(xml).getroot().iter('testsuite'))
        counts = {key: sum(int(s.get(key, 0)) for s in suites)
                  for key in ['tests', 'failures', 'errors', 'skipped']}
        evidence['runs'][name] = {**counts, 'exit_code': code}
        print(name, evidence['runs'][name], flush=True)
    evidence['passed'] = all(row['exit_code'] == 0 for row in evidence['runs'].values())
    (output/'Regression_Verification.json').write_text(json.dumps(evidence, indent=2))
    return 0 if evidence['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
