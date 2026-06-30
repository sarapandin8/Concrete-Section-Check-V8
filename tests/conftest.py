"""Pytest-only compatibility helpers.

The production app depends on Streamlit, but several CI/sandbox runners used for
kernel and source-audit tests do not install UI runtime packages.  These tests do
not render a live Streamlit app; they only import modules or monkeypatch specific
widgets.  Provide a tiny import-time fallback so non-UI QA gates remain runnable
without weakening the production dependency declared in requirements.txt.
"""

from __future__ import annotations

import contextlib
import sys
import types
from typing import Any


class _SessionState(dict):
    """Small dict with attribute access, close enough for import-only tests."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:  # pragma: no cover - standard attribute protocol
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class _DummyColumnConfig:
    def TextColumn(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"type": "TextColumn", "args": args, "kwargs": kwargs}

    def NumberColumn(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"type": "NumberColumn", "args": args, "kwargs": kwargs}

    def CheckboxColumn(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"type": "CheckboxColumn", "args": args, "kwargs": kwargs}

    def SelectboxColumn(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"type": "SelectboxColumn", "args": args, "kwargs": kwargs}


@contextlib.contextmanager
def _null_context(*args: Any, **kwargs: Any):
    yield None


class _StreamlitStub(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("streamlit")
        self.session_state = _SessionState()
        self.column_config = _DummyColumnConfig()
        self.sidebar = types.SimpleNamespace(
            selectbox=lambda *args, **kwargs: kwargs.get("options", [None])[0]
            if kwargs.get("options")
            else None,
            radio=lambda *args, **kwargs: kwargs.get("options", [None])[0]
            if kwargs.get("options")
            else None,
            markdown=lambda *args, **kwargs: None,
            button=lambda *args, **kwargs: False,
        )

    def cache_data(self, func: Any = None, **cache_kwargs: Any) -> Any:
        def decorator(inner: Any) -> Any:
            return inner

        return decorator(func) if callable(func) else decorator

    def tabs(self, labels: list[str] | tuple[str, ...]) -> list[Any]:
        return [_null_context() for _ in labels]

    def columns(self, spec: Any, *args: Any, **kwargs: Any) -> list[Any]:
        count = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        return [_null_context() for _ in range(count)]

    def expander(self, *args: Any, **kwargs: Any) -> Any:
        return _null_context()

    def container(self, *args: Any, **kwargs: Any) -> Any:
        return _null_context()

    def form(self, *args: Any, **kwargs: Any) -> Any:
        return _null_context()

    def __getattr__(self, name: str) -> Any:
        if name in {"data_editor", "dataframe"}:
            return lambda data=None, *args, **kwargs: data
        if name in {"button", "form_submit_button", "toggle", "checkbox"}:
            return lambda *args, **kwargs: bool(kwargs.get("value", False))
        if name in {"selectbox", "radio", "segmented_control"}:
            return lambda *args, **kwargs: kwargs.get("options", [None])[0] if kwargs.get("options") else None
        if name in {"number_input", "slider"}:
            return lambda *args, **kwargs: kwargs.get("value", 0.0)
        if name in {"text_input", "text_area"}:
            return lambda *args, **kwargs: kwargs.get("value", "")
        return lambda *args, **kwargs: None


if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = _StreamlitStub()
