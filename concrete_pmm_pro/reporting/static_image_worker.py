"""Private line-protocol worker. Run as a file to avoid loading the app."""
from pathlib import Path
import json
import sys


def main():
    import plotly.io as pio
    if getattr(pio.kaleido, 'scope', None) is not None:
        pio.kaleido.scope.mathjax = None
        # Kaleido's documented low-resource profile: keep the original safety
        # and shared-memory flags, adding a single Chromium process.
        flags = tuple(pio.kaleido.scope.chromium_args)
        if '--single-process' not in flags:
            pio.kaleido.scope.chromium_args = (*flags, '--single-process')
    output = Path(sys.argv[1]) / 'frame.png'
    for line in sys.stdin:
        request_id = None
        try:
            request = json.loads(line)
            request_id = request['id']
            # Already validated by the parent's Plotly Figure; keep the same
            # pinned renderer, layout, resolution and trace values.
            data = pio.to_image(request['figure'], format='png', validate=False)
            output.write_bytes(data)
            response = {'id': request_id, 'ok': True}
            del data, request
        except Exception as exc:
            response = {'id': request_id, 'ok': False, 'warning': str(exc)}
        print(json.dumps(response), flush=True)


if __name__ == '__main__':
    main()
