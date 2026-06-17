import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INSTALL = REPO / "install.py"


def load_install():
    spec = importlib.util.spec_from_file_location("install_under_test", INSTALL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fake_skill(root, name, with_refs=True):
    d = root / name
    (d / "scripts").mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: {0}\n---\nbody\n".format(name))
    (d / "scripts" / "x.py").write_text("# script\n")
    if with_refs:
        (d / "references").mkdir()
        (d / "references" / "r.md").write_text("# ref\n")
    return d


def test_discover_skips_underscore(tmp_path):
    mod = load_install()
    skills = tmp_path / "skills"
    skills.mkdir()
    fake_skill(skills, "deye-cloud")
    fake_skill(skills, "deye-cloud-daily")
    tmpl = skills / "_template"
    (tmpl).mkdir()
    (tmpl / "SKILL.md").write_text("x")
    names = [p.name for p in mod.discover_skills(skills)]
    assert "deye-cloud" in names
    assert "deye-cloud-daily" in names
    assert "_template" not in names


def test_resolve_base_scopes(tmp_path):
    mod = load_install()
    assert mod.resolve_base("global", None) == Path.home()
    assert mod.resolve_base("local", None) == Path.cwd()
    assert mod.resolve_base("local", str(tmp_path)) == tmp_path.resolve()
    # explicit target overrides scope
    assert mod.resolve_base("global", str(tmp_path)) == tmp_path.resolve()


def test_install_skill_copies_tree(tmp_path):
    mod = load_install()
    src_root = tmp_path / "src" / "skills"
    src_root.mkdir(parents=True)
    skill = fake_skill(src_root, "deye-cloud")
    dest = tmp_path / "out" / "skills"
    assert mod.install_skill(skill, dest, dry_run=False) is True
    assert (dest / "deye-cloud" / "SKILL.md").is_file()
    assert (dest / "deye-cloud" / "scripts" / "x.py").is_file()
    assert (dest / "deye-cloud" / "references" / "r.md").is_file()


def test_install_skill_dry_run_writes_nothing(tmp_path):
    mod = load_install()
    src_root = tmp_path / "src" / "skills"
    src_root.mkdir(parents=True)
    skill = fake_skill(src_root, "deye-cloud")
    dest = tmp_path / "out" / "skills"
    assert mod.install_skill(skill, dest, dry_run=True) is True
    assert not (dest / "deye-cloud").exists()


def test_cli_local_install_integration(tmp_path):
    # Runs the real installer against the repo's skills/ into a temp target.
    result = subprocess.run(
        [sys.executable, str(INSTALL), "--scope", "local", "--target", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    dest = tmp_path / ".claude" / "skills"
    assert (dest / "deye-cloud" / "SKILL.md").is_file()
    assert (dest / "deye-cloud-daily" / "scripts" / "_bootstrap.py").is_file()
    assert not (dest / "_template").exists()


def test_cli_dry_run_writes_nothing(tmp_path):
    result = subprocess.run(
        [sys.executable, str(INSTALL),
         "--scope", "local", "--target", str(tmp_path), "--dry-run"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / ".claude").exists()
