from __future__ import annotations

from pathlib import Path


def test_example_config_and_docs_are_checked_in():
    root = Path(__file__).resolve().parents[1]
    example_config = root / "examples" / "odooctl.yml"
    examples_doc = root / "docs" / "examples.md"

    assert example_config.exists(), "expected example config template to be checked in"
    assert examples_doc.exists(), "expected workflow docs to be checked in"

    config_text = example_config.read_text()
    doc_text = examples_doc.read_text()

    assert "project:" in config_text
    assert "environments:" in config_text
    assert "odooctl clone production staging --sanitize" in doc_text
    assert "odooctl status --config odooctl.yml --environment production --json" in doc_text
