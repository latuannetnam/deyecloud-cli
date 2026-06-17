import importlib.util
import os
from pathlib import Path

import pytest

BOOTSTRAP = (
    Path(__file__).resolve().parents[1]
    / "skills" / "_template" / "scripts" / "_bootstrap.py"
)


def load_bootstrap():
    """Load _bootstrap.py without triggering its module-level install()."""
    os.environ["DEYE_BOOTSTRAP_NOAUTO"] = "1"
    spec = importlib.util.spec_from_file_location("_bootstrap_under_test", BOOTSTRAP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_layout(tmp_path, with_core=True):
    """Build skills/deye-cloud/scripts + skills/deye-cloud-daily/scripts."""
    core_scripts = tmp_path / "skills" / "deye-cloud" / "scripts"
    daily_scripts = tmp_path / "skills" / "deye-cloud-daily" / "scripts"
    core_scripts.mkdir(parents=True)
    daily_scripts.mkdir(parents=True)
    if with_core:
        (core_scripts / "deye_core.py").write_text("# core\n")
    start = daily_scripts / "_bootstrap.py"
    start.write_text("# placeholder\n")
    return start, core_scripts


def test_sibling_resolves(tmp_path):
    mod = load_bootstrap()
    start, core = make_layout(tmp_path, with_core=True)
    assert mod.find_core_dir(start_file=str(start), environ={}) == core.resolve()


def test_env_override_wins(tmp_path):
    mod = load_bootstrap()
    start, core = make_layout(tmp_path, with_core=True)
    override = tmp_path / "custom_core"
    override.mkdir()
    (override / "deye_core.py").write_text("# core\n")
    found = mod.find_core_dir(
        start_file=str(start), environ={"DEYE_CORE_DIR": str(override)}
    )
    assert found == override.resolve()


def test_missing_returns_none(tmp_path):
    mod = load_bootstrap()
    start, _ = make_layout(tmp_path, with_core=False)
    assert mod.find_core_dir(start_file=str(start), environ={}) is None


def test_wants_json_detects_forms():
    mod = load_bootstrap()
    assert mod.wants_json(["--json"]) is True
    assert mod.wants_json(["--output", "json"]) is True
    assert mod.wants_json(["--output=json"]) is True
    assert mod.wants_json(["-o", "json"]) is True
    assert mod.wants_json(["--output", "text"]) is False
    assert mod.wants_json(["status"]) is False


def test_build_error_lists_paths_and_remedy():
    mod = load_bootstrap()
    msg = mod.build_error([("$DEYE_CORE_DIR", "(unset)"), ("sibling", "/x/y")])
    assert "DEYE_CORE_DIR" in msg
    assert "/x/y" in msg
    assert "DEYE_CORE_DIR" in msg and "suite" in msg.lower()


def test_fail_json_exits_nonzero(capsys):
    mod = load_bootstrap()
    with pytest.raises(SystemExit) as ei:
        mod.fail([("sibling", "/x/y")], argv=["--json"])
    assert ei.value.code == 1
    assert '"error"' in capsys.readouterr().out


def test_fail_text_exits_nonzero(capsys):
    mod = load_bootstrap()
    with pytest.raises(SystemExit) as ei:
        mod.fail([("sibling", "/x/y")], argv=["--output", "text"])
    assert ei.value.code == 1
    assert "deye_core" in capsys.readouterr().err
