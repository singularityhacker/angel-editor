import pytest


@pytest.fixture(autouse=True)
def no_real_visual_models(monkeypatch):
    """Tests opt into fake visual backends; never load or download real weights."""
    monkeypatch.setattr("angel_editor.visual.pipeline.available", lambda: False)
    monkeypatch.setattr("angel_editor.cli.available", lambda: False)
