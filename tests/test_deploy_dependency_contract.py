from pathlib import Path


def test_streamlit_starlette_compatibility_is_pinned() -> None:
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8")
    lines = {
        line.strip()
        for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "streamlit==1.61.0" in lines
    assert "starlette==1.3.1" in lines
    assert not any(line.startswith("streamlit>=") for line in lines)
