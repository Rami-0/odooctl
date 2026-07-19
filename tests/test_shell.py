import sys

from odooctl.utils.shell import join_csv, redact, run_capture_bytes, run_pipe_stdin


def test_join_csv_strips_empty_values():
    assert join_csv([" sale", "", "stock "]) == "sale,stock"


def test_redact_masks_sensitive_environment_values():
    env = {"ODOO_DB_PASSWORD": "supersecret", "NORMAL": "visible"}
    assert redact("password=supersecret normal=visible", env) == "password=***REDACTED*** normal=visible"


def test_run_capture_bytes_preserves_binary_stdout(tmp_path):
    output = tmp_path / "dump.bin"
    payload = b"\x00\xffbinary\nsecret"

    run_capture_bytes(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(bytes([0,255])+b'binary\\nsecret')"],
        stdout_path=output,
        env={"ODOO_DB_PASSWORD": "secret"},
    )

    assert output.read_bytes() == payload


def test_run_pipe_stdin_preserves_binary_stdin(tmp_path):
    input_path = tmp_path / "dump.bin"
    input_path.write_bytes(b"\x00\xffbinary")

    result = run_pipe_stdin(
        [sys.executable, "-c", "import sys; data=sys.stdin.buffer.read(); print(len(data)); sys.stderr.write(str(data[1]))"],
        stdin_path=input_path,
    )

    assert result.stdout.strip() == "8"
    assert result.stderr == "255"


def test_redact_skips_short_and_ignored_values():
    env = {"ODOO_DB_PASSWORD": "odoo", "API_TOKEN": "abc", "LONG_SECRET": "very-long-secret-value"}
    text = "odoo abc very-long-secret-value"

    assert redact(text, env) == "odoo abc ***REDACTED***"


def test_redact_allows_custom_policy():
    env = {"ODOO_DB_PASSWORD": "odoo"}

    assert redact("password=odoo", env, min_secret_length=4, ignore_values=[]) == "password=***REDACTED***"

def test_run_pipe_streams_producer_stdout_to_consumer():
    from odooctl.utils.shell import run_pipe

    result = run_pipe(["printf", "a\nb\nc\n"], ["wc", "-l"])
    assert result.returncode == 0
    assert result.stdout.strip() == "3"


def test_run_pipe_raises_on_consumer_failure():
    import pytest

    from odooctl.utils.shell import CommandError, run_pipe

    with pytest.raises(CommandError):
        run_pipe(["printf", "x"], ["false"])


def test_run_pipe_raises_on_producer_failure():
    import pytest

    from odooctl.utils.shell import CommandError, run_pipe

    with pytest.raises(CommandError) as excinfo:
        run_pipe(["sh", "-c", "exit 3"], ["cat"])
    assert excinfo.value.result.returncode == 3


def test_run_pipe_does_not_shell_interpret_operands(tmp_path):
    from odooctl.utils.shell import run_pipe

    marker = tmp_path / "pwned"
    result = run_pipe(["echo", f"$(touch {marker}); true"], ["cat"])
    assert result.returncode == 0
    assert not marker.exists()


def test_no_shell_dash_c_sinks_in_source_tree():
    """Guard: adapters/services must never build 'sh -c' / 'sh -lc' command strings."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "odooctl"
    offenders = []
    for path in root.rglob("*.py"):
        text = path.read_text()
        if '"sh", "-lc"' in text or '"sh", "-c"' in text or "'sh', '-lc'" in text or "'sh', '-c'" in text:
            offenders.append(str(path))
    assert offenders == [], f"shell -c sinks found: {offenders}"
