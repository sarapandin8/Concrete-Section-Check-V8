"""Bounded static export with one active isolated renderer per report."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
from queue import Empty, Queue
import signal
import subprocess
import sys
import tempfile
from threading import RLock, Thread
from typing import Any

_EXPORT_LOCK = RLock()
_RENDERER = ContextVar('report_static_renderer', default=None)
_PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
# Chromium retains rendering allocations. Recycle between small batches while
# keeping only one process tree alive and avoiding a cold start for every image.
MAX_FIGURES_PER_WORKER = 8


def plotly_figure_to_html_bytes(fig: Any) -> bytes:
    return fig.to_html(full_html=True, include_plotlyjs="cdn").encode("utf-8")


@contextmanager
def report_export_slot():
    """Do not allocate several complete reports/Chromium trees concurrently."""
    if not _EXPORT_LOCK.acquire(timeout=5.):
        raise RuntimeError('Another report is being prepared. Please retry when it finishes.')
    try:
        yield
    finally:
        _EXPORT_LOCK.release()


def _terminate_process_tree(process: subprocess.Popen) -> None:
    """Kill only the process group created for this export, then reap it."""
    if os.name == 'nt':
        if process.poll() is None:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, check=False, timeout=5)
    else:
        # The worker is started in its own session. Its leader may already have
        # exited while Kaleido/Chromium descendants are still running.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


class _StaticImageRenderer:
    def __init__(self):
        self.process = None
        self.directory = None
        self.stderr = None
        self.request_id = 0
        self.frames = 0
        self.failure = None

    def _start(self):
        self.directory = tempfile.TemporaryDirectory(prefix='concrete-report-')
        self.stderr = tempfile.TemporaryFile(mode='w+b')
        self.process = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name('static_image_worker.py')),
             self.directory.name], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.stderr, text=True, encoding='utf-8', bufsize=1,
            start_new_session=(os.name != 'nt'))

    def render(self, fig, timeout_seconds):
        if self.failure:
            return None, [self.failure]
        try:
            if self.frames >= MAX_FIGURES_PER_WORKER:
                self.close()
            if self.process is None:
                self._start()
            self.request_id += 1
            request_id = self.request_id
            # Cover a blocked stdin write and a stalled response with one deadline.
            request = '{"id":' + str(request_id) + ',"figure":' + fig.to_json() + '}\n'
            replies = Queue(maxsize=1)
            process = self.process
            def exchange():
                try:
                    process.stdin.write(request)
                    process.stdin.flush()
                    replies.put((process.stdout.readline(), None))
                except Exception as exc:
                    replies.put((None, exc))
            thread = Thread(target=exchange, name='report-image-pipe', daemon=True)
            thread.start()
            try:
                line, error = replies.get(timeout=max(.001, timeout_seconds))
            except Empty:
                raise TimeoutError(f'export timed out after {timeout_seconds:g} seconds')
            if error:
                raise error
            if not line:
                self.stderr.seek(0, 2)
                size = self.stderr.tell()
                self.stderr.seek(max(0, size-2000))
                detail = self.stderr.read().decode('utf-8', errors='replace').strip()
                raise RuntimeError(detail or 'static image worker stopped without a response')
            response = json.loads(line)
            if response.get('id') != request_id:
                raise RuntimeError('static image worker returned an unexpected response')
            if not response.get('ok'):
                raise RuntimeError(response.get('warning') or 'PNG export returned no image data')
            path = Path(self.directory.name) / 'frame.png'
            data = path.read_bytes()
            path.unlink()
            if not data.startswith(_PNG_SIGNATURE):
                raise RuntimeError('static image worker returned invalid PNG data')
            self.frames += 1
            return data, []
        except Exception as exc:
            self.failure = 'PNG export requires kaleido. HTML export remains available. Detail: ' + str(exc)
            self.close()
            return None, [self.failure]

    def close(self):
        self.frames = 0
        process, self.process = self.process, None
        if process is not None:
            try:
                _terminate_process_tree(process)
            finally:
                for pipe in (process.stdin, process.stdout):
                    if pipe is not None:
                        try:
                            pipe.close()
                        except OSError:
                            pass
        if self.stderr is not None:
            self.stderr.close()
            self.stderr = None
        if self.directory is not None:
            self.directory.cleanup()
            self.directory = None


@contextmanager
def static_image_export_session():
    """Reuse a lazy renderer for sequential figures; always clean up on exit."""
    existing = _RENDERER.get()
    if existing is not None:
        yield existing
        return
    with report_export_slot():
        renderer = _StaticImageRenderer()
        token = _RENDERER.set(renderer)
        try:
            yield renderer
        finally:
            _RENDERER.reset(token)
            renderer.close()


def plotly_figure_to_png_bytes(fig: Any, timeout_seconds: float = 20.0) -> tuple[bytes | None, list[str]]:
    """Return PNG or a bounded failure, without leaving renderer descendants."""
    with static_image_export_session() as renderer:
        return renderer.render(fig, timeout_seconds)
