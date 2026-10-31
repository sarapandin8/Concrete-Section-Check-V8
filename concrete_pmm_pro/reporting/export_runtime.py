"""Small, read-only Cloud diagnostics and an early low-headroom export guard."""
import gc
from pathlib import Path
import platform
from importlib.metadata import version

RELEASE = 'REPORT.CLOUD86'


class ReportResourceError(RuntimeError):
    pass


def memory_snapshot():
    result = {}
    try:
        for line in Path('/proc/self/status').read_text().splitlines():
            if line.startswith('VmRSS:'):
                result['app_rss_mib'] = round(int(line.split()[1])/1024, 1)
                break
    except (OSError,ValueError,IndexError):
        pass
    candidates = [('/sys/fs/cgroup/memory.current','/sys/fs/cgroup/memory.max'),
        ('/sys/fs/cgroup/memory/memory.usage_in_bytes',
         '/sys/fs/cgroup/memory/memory.limit_in_bytes')]
    for current, limit in candidates:
        try:
            used = int(Path(current).read_text().strip())
            maximum = int(Path(limit).read_text().strip())
            if 0 < maximum < 2**60 and used >= 0:
                result.update(container_used_mib=round(used/1024**2,1),
                    container_limit_mib=round(maximum/1024**2,1),
                    container_headroom_mib=round((maximum-used)/1024**2,1))
                break
        except (OSError,ValueError):
            continue
    return result


def check_export_headroom(minimum_mib=96.):
    """Stop cleanly before another large allocation when a cgroup is nearly full.

    No estimate is made when Cloud does not expose its memory accounting. This
    guard cannot guarantee protection from a sudden native allocation or OOM.
    """
    snapshot = memory_snapshot()
    if snapshot.get('container_headroom_mib', float('inf')) < minimum_mib:
        gc.collect()
        snapshot = memory_snapshot()
        if snapshot.get('container_headroom_mib', float('inf')) < minimum_mib:
            raise ReportResourceError('Report export stopped because the app container has '
                f"only {snapshot['container_headroom_mib']:.1f} MiB of memory headroom "
                f"({snapshot['container_used_mib']:.1f}/{snapshot['container_limit_mib']:.1f} MiB used). "
                'Save your project inputs before rebooting. If this repeats after a fresh '
                'Analysis, the project needs a host with more memory. See the Cloud export log.')
    return snapshot


def environment_snapshot():
    return {'release':RELEASE,'python':platform.python_version(),
        **{name:version(name) for name in ('streamlit','pandas','plotly','kaleido','python-docx')},
        **memory_snapshot()}
